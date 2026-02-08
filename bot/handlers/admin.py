"""Admin broadcast handlers"""
import asyncio
import logging

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
from database.queries import (
    get_users_no_reports_no_payments,
    get_users_one_report_no_payments,
    get_users_single_purchase,
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
            text="❌ Выйти из админки",
            callback_data="admin_exit",
        )],
    ])


# ── /admin command ──────────────────────────────────────────────────────


@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    """Handle /admin – check access and show group selection."""
    user_id = message.from_user.id
    logger.info(f"[ADMIN] User {user_id} invoked /admin")

    if user_id not in settings.admin_id_list:
        logger.warning(f"[ADMIN] Access denied for user {user_id}")
        await message.answer("🚫 Админ-панель недоступна.")
        return

    await state.set_state(AdminStates.choosing_group)

    await message.answer(
        "🔧 <b>Админ-панель</b>\n\n"
        "Вы можете отправить сообщение определённой группе пользователей.\n"
        "Выберите группу:",
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
        [InlineKeyboardButton(text="⬅️ Назад к выбору группы", callback_data="admin_back_to_groups")],
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
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_cancel")],
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
        [InlineKeyboardButton(text="⬅️ Назад к выбору группы", callback_data="admin_back_to_groups")],
        [InlineKeyboardButton(text="❌ Выйти из админки", callback_data="admin_exit")],
    ])

    await callback.message.answer(
        f"📝 <b>Группа:</b> {GROUP_LABELS.get(group_key, '—')}\n\n"
        "Введите новое сообщение для рассылки:",
        reply_markup=keyboard,
    )


# ── Navigation helpers ──────────────────────────────────────────────────


@router.callback_query(F.data == "admin_back_to_groups")
async def back_to_groups(callback: CallbackQuery, state: FSMContext):
    """Return to group selection screen."""
    logger.info(f"[ADMIN] User {callback.from_user.id} navigated back to group selection")
    await callback.answer()
    await state.set_state(AdminStates.choosing_group)

    await callback.message.answer(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите группу пользователей:",
        reply_markup=_build_group_selection_keyboard(),
    )


@router.callback_query(F.data == "admin_exit")
async def exit_admin(callback: CallbackQuery, state: FSMContext):
    """Exit admin panel – clear state."""
    await callback.answer("Вышли из админки", show_alert=True)
    await state.clear()
    await callback.message.delete()
    logger.info(f"[ADMIN] User {callback.from_user.id} exited admin panel")
