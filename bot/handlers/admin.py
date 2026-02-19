"""Admin broadcast handlers"""
import asyncio
import logging
from collections.abc import Awaitable, Callable

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot.config import settings
from bot.states import AdminStates
from database.models import EventType, User
from database.queries import (
    get_users_no_reports_no_payments,
    get_users_one_report_no_payments,
    get_users_single_purchase,
    count_unique_users_by_events,
    get_unique_user_ids_by_events,
    get_usernames_by_ids,
)

logger = logging.getLogger(__name__)

router = Router()

# User segment labels for display
GROUP_LABELS = {
    "no_activity": "Нажали /start, но не сделали ни одного отчета",
    "used_trial": "Использовали пробный отчет, но не покупали",
    "bought_single": "Купили ровно один отчет",
}

# Mapping from group key to query function
GROUP_QUERY_MAP = {
    "no_activity": get_users_no_reports_no_payments,
    "used_trial": get_users_one_report_no_payments,
    "bought_single": get_users_single_purchase,
}

ConversionSource = list[EventType] | Callable[[], Awaitable[list[int]]]

CONVERSION_CATEGORIES: dict[int, tuple[str, ConversionSource]] = {
    1: ("Зашли в бота", [EventType.CLICK_START]),
    2: ('Нажали "Баланс"', [EventType.CLICK_BALANCE]),
    3: ('Нажали "Сравнить карточки"', [EventType.CLICK_COMPARE]),
    4: ("Ввели артикулы", [EventType.ENTER_ARTICLES]),
    5: ('Выбрали опцию "Один отчет"', [EventType.CLICK_SINGLE]),
    6: ('Выбрали опцию "Пакет"', [EventType.CLICK_PACKET]),
    7: ("Выбрали любую из опций", [EventType.CLICK_PACKET, EventType.CLICK_SINGLE]),
    8: ("Сделали покупку", [EventType.PAY_FOR_OPTION]),
    9: ('Нажали "Реферальная ссылка"', [EventType.CLICK_REFERRAL_LINK]),
    10: ("Использовали пробный отчет, но не покупали", get_users_one_report_no_payments),
}


def _build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build main admin menu keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Посмотреть конверсии",
            callback_data="admin_conversions",
        )],
        [InlineKeyboardButton(
            text="👤 Показать ники пользователей",
            callback_data="admin_usernames",
        )],
        [InlineKeyboardButton(
            text="📨 Сделать рассылку",
            callback_data="admin_broadcast",
        )],
        [InlineKeyboardButton(
            text="❌ Выйти из админки",
            callback_data="admin_exit",
        )],
    ])


def _build_group_selection_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting a user segment."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👤 Без отчетов",
            callback_data="admin_group:no_activity",
        )],
        [InlineKeyboardButton(
            text="📄 Использовали пробный",
            callback_data="admin_group:used_trial",
        )],
        [InlineKeyboardButton(
            text="💳 Купили 1 отчет",
            callback_data="admin_group:bought_single",
        )],
        [InlineKeyboardButton(
            text="⬅️ Главное меню",
            callback_data="admin_back_to_main",
        )],
    ])


# ── /admin command ──────────────────────────────────────────────────────


@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    """Handle /admin – check access and show main menu."""
    user_id = message.from_user.id
    logger.info(f"[ADMIN] User {user_id} invoked /admin")

    if user_id not in settings.admin_id_list:
        logger.warning(f"[ADMIN] Access denied for user {user_id}")
        await message.answer("🚫 Админ-панель недоступна.")
        return

    await state.set_state(AdminStates.main_menu)

    await message.answer(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=_build_main_menu_keyboard(),
    )


# ── Main menu callbacks ─────────────────────────────────────────────────


@router.callback_query(AdminStates.main_menu, F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Show user group selection for broadcast."""
    admin_id = callback.from_user.id
    logger.info(f"[ADMIN] User {admin_id} opened broadcast menu")
    await callback.answer()
    await state.set_state(AdminStates.choosing_group)

    await callback.message.answer(
        "📨 <b>Выберите группу пользователей</b>",
        reply_markup=_build_group_selection_keyboard(),
    )


# ── Group selection callbacks ───────────────────────────────────────────


@router.callback_query(AdminStates.choosing_group, F.data.startswith("admin_group:"))
async def group_selected(callback: CallbackQuery, state: FSMContext):
    """Handle group button press – count users and ask admin to type the message."""
    group_key = callback.data.split(":", 1)[1]
    admin_id = callback.from_user.id
    logger.info(f"[ADMIN] User {admin_id} selected group '{group_key}'")

    if group_key not in GROUP_LABELS:
        logger.warning(f"[ADMIN] Unknown group key '{group_key}' from user {admin_id}")
        await callback.answer("Неизвестная группа", show_alert=True)
        return

    await callback.answer()

    # Count users in the selected group
    query_fn = GROUP_QUERY_MAP.get(group_key)
    user_ids = await query_fn() if query_fn else []
    user_count = len(user_ids)
    logger.info(f"[ADMIN] Group '{group_key}' has {user_count} users")

    # Store chosen group in FSM data
    await state.update_data(group_key=group_key)
    await state.set_state(AdminStates.entering_message)
    logger.info(f"[ADMIN] User {admin_id} → entering_message for group '{group_key}'")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к выбору группы", callback_data="admin_back_to_broadcast")],
        [InlineKeyboardButton(text="❌ Выйти из админки", callback_data="admin_exit")],
    ])

    await callback.message.answer(
        f"📝 <b>Группа:</b> {GROUP_LABELS[group_key]}\n"
        f"👥 <b>Пользователей в группе:</b> {user_count}\n\n"
        "Введите сообщение, которое хотите отправить всем пользователям этой группы:",
        reply_markup=keyboard,
    )


# ── Message input ───────────────────────────────────────────────────────


@router.message(AdminStates.entering_message, F.text)
async def message_entered(message: Message, state: FSMContext):
    """Store the broadcast text and ask for confirmation."""
    admin_id = message.from_user.id
    broadcast_text = message.text
    logger.info(
        f"[ADMIN] User {admin_id} entered broadcast text "
        f"({len(broadcast_text)} chars): {broadcast_text[:80]}{'...' if len(broadcast_text) > 80 else ''}"
    )

    await state.update_data(broadcast_text=broadcast_text)
    await state.set_state(AdminStates.confirming_message)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить отправку", callback_data="admin_confirm")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_cancel")],
    ])

    await message.answer(
        "📨 <b>Предпросмотр сообщения:</b>\n\n"
        f"{broadcast_text}\n\n"
        "Подтверждаете отправку этого сообщения?",
        reply_markup=keyboard,
    )


# ── Confirmation / Cancel ───────────────────────────────────────────────


@router.callback_query(AdminStates.confirming_message, F.data == "admin_confirm")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    """Broadcast the message to all users in the selected group."""
    admin_id = callback.from_user.id
    await callback.answer()

    data = await state.get_data()
    group_key: str = data["group_key"]
    broadcast_text: str = data["broadcast_text"]
    logger.info(f"[ADMIN] User {admin_id} confirmed broadcast for group '{group_key}'")

    query_fn = GROUP_QUERY_MAP.get(group_key)
    if query_fn is None:
        logger.error(f"[ADMIN] No query function for group '{group_key}'")
        await callback.message.answer("❌ Ошибка: неизвестная группа.")
        await state.clear()
        return

    # Notify admin that sending started
    await callback.message.answer(
        f"⏳ Отправка сообщения группе <b>{GROUP_LABELS[group_key]}</b>...\n"
        "Пожалуйста, подождите."
    )

    # Fetch user IDs
    logger.info(f"[ADMIN] Fetching user IDs for group '{group_key}'...")
    user_ids = await query_fn()
    logger.info(f"[ADMIN] Found {len(user_ids)} users in group '{group_key}'")

    if not user_ids:
        logger.info(f"[ADMIN] No users in group '{group_key}', broadcast skipped")
        await callback.message.answer(
            "ℹ️ В выбранной группе нет пользователей. Рассылка не выполнена."
        )
        await state.clear()
        return

    bot = callback.bot
    sent = 0
    failed = 0
    failed_uids: list[int] = []

    logger.info(f"[ADMIN] Starting broadcast to {len(user_ids)} users...")
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=broadcast_text)
            sent += 1
        except Exception as e:
            logger.warning(f"[ADMIN] Failed to send to {uid}: {e}")
            failed += 1
            failed_uids.append(uid)

        # Respect Telegram rate limits (~30 msg/sec)
        await asyncio.sleep(0.05)

    logger.info(
        f"[ADMIN] Broadcast done by {admin_id}: "
        f"group='{group_key}', total={len(user_ids)}, sent={sent}, failed={failed}"
    )
    if failed_uids:
        logger.warning(f"[ADMIN] Failed user IDs: {failed_uids}")

    await callback.message.answer(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"Группа: {GROUP_LABELS[group_key]}\n"
        f"Отправлено: <b>{sent}</b>\n"
        f"Ошибок: <b>{failed}</b>"
    )

    await state.clear()


@router.callback_query(AdminStates.confirming_message, F.data == "admin_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Cancel confirmation – go back to entering message."""
    admin_id = callback.from_user.id
    await callback.answer()

    data = await state.get_data()
    group_key: str = data.get("group_key", "")
    logger.info(f"[ADMIN] User {admin_id} canceled broadcast for group '{group_key}'")

    await state.set_state(AdminStates.entering_message)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к выбору группы", callback_data="admin_back_to_broadcast")],
        [InlineKeyboardButton(text="❌ Выйти из админки", callback_data="admin_exit")],
    ])

    await callback.message.answer(
        f"📝 <b>Группа:</b> {GROUP_LABELS.get(group_key, '—')}\n\n"
        "Введите новое сообщение для рассылки:",
        reply_markup=keyboard,
    )


# ── Conversion analytics ─────────────────────────────────────────────────


def _build_conversion_categories_text() -> str:
    """Build the numbered list of conversion categories."""
    lines = ["<b>Выберите категории пользователей, для которых посчитать конверсию</b>\n"]
    for num, (label, _) in CONVERSION_CATEGORIES.items():
        lines.append(f"{num}. {label}")
    lines.append("\nВведите номера категорий через запятую.\n💡 Пример: <code>1,7</code>")
    return "\n".join(lines)


@router.callback_query(AdminStates.main_menu, F.data == "admin_conversions")
async def conversions_start(callback: CallbackQuery, state: FSMContext):
    """Show conversion categories and wait for input."""
    admin_id = callback.from_user.id
    logger.info(f"[ADMIN] User {admin_id} opened conversions")
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_conversion_categories)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Меню админки", callback_data="admin_back_to_main")],
    ])

    await callback.message.answer(
        _build_conversion_categories_text(),
        reply_markup=keyboard,
    )


@router.message(AdminStates.waiting_for_conversion_categories, F.text)
async def conversions_process(message: Message, state: FSMContext):
    """Validate input, count users, and display conversion results."""
    admin_id = message.from_user.id
    args_text = (message.text or "").strip()

    if not args_text:
        await message.answer(
            "❌ <b>Не указаны номера категорий</b>\n\n"
            "Введите номера через запятую.\n\n"
            "💡 Пример: <code>1,7</code>"
        )
        return

    try:
        parts = [p.strip() for p in args_text.split(",")]
        numbers = [int(p) for p in parts if p]
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Номера категорий должны быть числами, разделёнными запятыми.\n\n"
            "💡 Пример: <code>1,7</code>"
        )
        return

    if not numbers:
        await message.answer(
            "❌ <b>Не указаны номера категорий</b>\n\n"
            "Введите номера через запятую.\n\n"
            "💡 Пример: <code>1,7</code>"
        )
        return

    seen = set()
    for n in numbers:
        if n in seen:
            await message.answer(
                f"❌ <b>Повторяющийся номер: {n}</b>\n\n"
                "Каждый номер категории должен быть уникальным."
            )
            return
        seen.add(n)

    invalid = [n for n in numbers if n not in CONVERSION_CATEGORIES]
    if invalid:
        max_num = max(CONVERSION_CATEGORIES)
        await message.answer(
            f"❌ <b>Неверные номера: {', '.join(map(str, invalid))}</b>\n\n"
            f"Допустимые номера от 1 до {max_num}."
        )
        return

    logger.info(f"[ADMIN] User {admin_id} requested conversions for categories {numbers}")

    # Fetch counts
    counts: dict[int, int] = {}
    for num in numbers:
        _, source = CONVERSION_CATEGORIES[num]
        if callable(source):
            counts[num] = len(await source())
        else:
            counts[num] = await count_unique_users_by_events(source)

    # Build result message
    lines = ["<b>Результаты</b>\n"]
    for num in numbers:
        label, _ = CONVERSION_CATEGORIES[num]
        lines.append(f"{num}. {label} — <b>{counts[num]}</b> пользователей")

    if len(numbers) >= 2:
        lines.append("\n<b>Конверсии</b>\n")
        for i in range(len(numbers) - 1):
            a, b = numbers[i], numbers[i + 1]
            count_a, count_b = counts[a], counts[b]
            if count_a > 0:
                pct = count_b / count_a * 100
                lines.append(f"{a} → {b}: <b>{pct:.1f}%</b>")
            else:
                lines.append(f"{a} → {b}: <b>н/д</b> (0 пользователей в категории {a})")

    lines.append("\n💡 Чтобы еще раз посчитать конверсию, введите числа.")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Меню админки", callback_data="admin_back_to_main")],
    ])

    await message.answer("\n".join(lines), reply_markup=keyboard)


# ── Username listing ──────────────────────────────────────────────────────

MAX_MESSAGE_LENGTH = 4000


def _build_usernames_categories_text() -> str:
    """Build the numbered list of categories for username listing."""
    lines = ["<b>Выберите категорию пользователей, чтобы посмотреть их ники</b>\n"]
    for num, (label, _) in CONVERSION_CATEGORIES.items():
        lines.append(f"{num}. {label}")
    lines.append("\nВведите номер категории.\n💡 Пример: <code>3</code>")
    return "\n".join(lines)


@router.callback_query(AdminStates.main_menu, F.data == "admin_usernames")
async def usernames_start(callback: CallbackQuery, state: FSMContext):
    """Show categories and wait for a single category number."""
    admin_id = callback.from_user.id
    logger.info(f"[ADMIN] User {admin_id} opened usernames listing")
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_usernames_category)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Меню админки", callback_data="admin_back_to_main")],
    ])

    await callback.message.answer(
        _build_usernames_categories_text(),
        reply_markup=keyboard,
    )


@router.message(AdminStates.waiting_for_usernames_category, F.text)
async def usernames_process(message: Message, state: FSMContext):
    """Validate single category number and list usernames."""
    admin_id = message.from_user.id
    args_text = (message.text or "").strip()

    if not args_text:
        await message.answer(
            "❌ <b>Не указан номер категории</b>\n\n"
            "Введите один номер.\n\n"
            "💡 Пример: <code>3</code>"
        )
        return

    try:
        num = int(args_text)
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Номер категории должен быть числом.\n\n"
            "💡 Пример: <code>3</code>"
        )
        return

    if num not in CONVERSION_CATEGORIES:
        max_num = max(CONVERSION_CATEGORIES)
        await message.answer(
            f"❌ <b>Неверный номер: {num}</b>\n\n"
            f"Допустимые номера от 1 до {max_num}."
        )
        return

    logger.info(f"[ADMIN] User {admin_id} requested usernames for category {num}")

    label, source = CONVERSION_CATEGORIES[num]

    if callable(source):
        user_ids = await source()
    else:
        user_ids = await get_unique_user_ids_by_events(source)

    if not user_ids:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Меню админки", callback_data="admin_back_to_main")],
        ])
        await message.answer(
            f"<b>{num}. {label}</b>\n\n"
            "В этой категории нет пользователей.",
            reply_markup=keyboard,
        )
        return

    usernames = await get_usernames_by_ids(user_ids)

    items: list[str] = []
    for uid in user_ids:
        uname = usernames.get(uid)
        if uname:
            items.append(f"@{uname}")
        else:
            items.append(f"нет ника (ID: {uid})")

    header = f"<b>{num}. {label}</b>\nВсего: <b>{len(items)}</b>\n\n"

    chunks: list[str] = []
    current_lines: list[str] = []
    current_len = len(header)
    idx = 0

    for item in items:
        idx += 1
        line = f"{idx}. {item}"
        line_len = len(line) + 1  # +1 for newline
        if current_lines and current_len + line_len > MAX_MESSAGE_LENGTH:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_len = line_len
        else:
            current_lines.append(line)
            current_len += line_len

    if current_lines:
        chunks.append("\n".join(current_lines))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Меню админки", callback_data="admin_back_to_main")],
    ])

    for i, chunk in enumerate(chunks):
        text = header + chunk if i == 0 else chunk
        is_last = i == len(chunks) - 1
        await message.answer(text, reply_markup=keyboard if is_last else None)

    logger.info(
        f"[ADMIN] Sent {len(chunks)} message(s) with {len(items)} usernames "
        f"for category {num} to user {admin_id}"
    )


# ── Navigation helpers ──────────────────────────────────────────────────


@router.callback_query(F.data == "admin_back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Return to main admin menu."""
    logger.info(f"[ADMIN] User {callback.from_user.id} navigated back to main menu")
    await callback.answer()
    await state.set_state(AdminStates.main_menu)

    await callback.message.answer(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=_build_main_menu_keyboard(),
    )


@router.callback_query(F.data == "admin_back_to_broadcast")
async def back_to_broadcast(callback: CallbackQuery, state: FSMContext):
    """Return to group selection screen for broadcast."""
    logger.info(f"[ADMIN] User {callback.from_user.id} navigated back to group selection")
    await callback.answer()
    await state.set_state(AdminStates.choosing_group)

    await callback.message.answer(
        "📨 <b>Выберите группу пользователей</b>",
        reply_markup=_build_group_selection_keyboard(),
    )


@router.callback_query(F.data == "admin_exit")
async def exit_admin(callback: CallbackQuery, state: FSMContext, user: User):
    """Exit admin panel – clear state and show start menu."""
    from bot.handlers.start import back_to_start_callback
    
    await state.clear()
    await callback.message.delete()
    logger.info(f"[ADMIN] User {callback.from_user.id} exited admin panel")
    
    await back_to_start_callback(callback, user)
