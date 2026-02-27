"""Start command handler"""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database.models import User, EventType, CreateEventDTO
from database.queries import create_event, count_referrals
from bot.utils import LoadingSticker

logger = logging.getLogger(__name__)

router = Router()


def build_start_menu(_user: User, first_name: str) -> tuple[str, InlineKeyboardMarkup]:
    """Build welcome text and main menu keyboard."""
    text = f"""
👋 Привет, {first_name}!

Вы здесь, потому что вам нужны <b>настоящие цифры</b> Wildberries, а не кривые.

В одном отчете ты получишь:
• <b>Реальный CTR и воронку</b> (Переходы → Корзины → Заказы).
• <b>Продающие ключи</b> (Узнаешь, по каким запросам реально покупают).
• <b>Региональную логистику</b> (Остатки и заказы по всем складам).

👇 Нажми кнопку, чтобы сформировать отчет.
"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Получить отчет", callback_data="compare_cards"
                ),
                InlineKeyboardButton(
                    text="💰 Пополнить баланс", callback_data="balance"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📄 Пример отчета", callback_data="show_example_report"
                )
            ],
            [
                InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/wifftees"),
                InlineKeyboardButton(
                    text="🔗 Реферальная программа", callback_data="referral_link"
                ),
            ],
        ]
    )
    return text, keyboard


@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    """Handle /start command"""
    logger.info(f"User {user.id} started the bot")

    async with LoadingSticker(message, message.bot):
        # Extract referrer ID from deep link if present
        if message.text and message.text.startswith("/start "):
            try:
                args = message.text.split(maxsplit=1)[1]
                _referrer_id = int(args)

            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to extract referrer_id from /start: {e}")

        # Track CLICK_START event
        await create_event(
            CreateEventDTO(user_id=user.id, event_type=EventType.CLICK_START)
        )

        welcome_text, keyboard = build_start_menu(user, message.from_user.first_name)

    await message.answer(welcome_text, reply_markup=keyboard)


@router.callback_query(F.data == "back_to_start")
async def back_to_start_callback(callback: CallbackQuery, user: User):
    """Handle back to start menu button click"""
    logger.info(f"User {user.id} returned to start menu")

    # Track CLICK_START event
    await create_event(
        CreateEventDTO(user_id=user.id, event_type=EventType.CLICK_START)
    )

    await callback.answer()

    welcome_text, keyboard = build_start_menu(user, callback.from_user.first_name)

    await callback.message.answer(welcome_text, reply_markup=keyboard)


@router.callback_query(F.data == "referral_link")
async def referral_link_callback(callback: CallbackQuery, user: User):
    """Show user their referral link"""
    logger.info(f"User {user.id} requested referral link")

    # Track CLICK_REFERRAL_LINK event
    await create_event(
        CreateEventDTO(user_id=user.id, event_type=EventType.CLICK_REFERRAL_LINK)
    )

    await callback.answer()

    bot_info = await callback.bot.get_me()
    referral_url = f"https://t.me/{bot_info.username}?start={user.id}"

    # Count referrals dynamically
    referral_count = await count_referrals(user.id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню", callback_data="back_to_start"
                )
            ]
        ]
    )

    await callback.message.answer(
        f"🔗 <b>Ваша реферальная ссылка:</b>\n\n"
        f'<a href="{referral_url}">Приглашаю в бота для сравнения карточек</a>\n\n'
        f"👥 Приглашено друзей: <b>{referral_count}</b>\n"
        f"💰 Реферальный баланс: <b>{user.referral_balance} ₽</b>\n\n"
        f"Зарабатывай вместе с нами!\n"
        f"💸 Стань партнером сервиса и получай пассивный доход с каждого отчета.\n\n"
        f"Расскажи о нашем боте.\n"
        f"Они получат пользу, а ты получишь 20% с каждого оплаченного ими отчета.\n\n"
        f"Условия:\n"
        f"✅ 20% с каждого оплаченного отчета, купленного по твоей ссылке.\n"
        f"✅ Мгновенное начисление на твой баланс в боте после оплаты.",
        reply_markup=keyboard,
    )
