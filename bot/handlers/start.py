"""Start command handler"""
import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.models import User, EventType, CreateEventDTO
from database.queries import create_event, update_user_invited_by
from bot.utils import LoadingSticker

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    """Handle /start command"""
    logger.info(f"User {user.id} started the bot")
    
    async with LoadingSticker(message, message.bot):
        # Extract referrer ID from deep link if present
        if message.text and message.text.startswith("/start "):
            try:
                args = message.text.split(maxsplit=1)[1]
                referrer_id = int(args)
                
                # Update invited_by if not already set
                if user.invited_by is None:
                    logger.info(f"Processing referral: user {user.id} invited by {referrer_id}")
                    await update_user_invited_by(user.id, referrer_id)
                else:
                    logger.debug(f"User {user.id} already has referrer: {user.invited_by}")
            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to extract referrer_id from /start: {e}")
        
        # Track CLICK_START event
        await create_event(CreateEventDTO(user_id=user.id, event_type=EventType.CLICK_START))
        
        welcome_text = f"""
👋 Привет, {message.from_user.first_name}!

Я бот для генерации отчетов Wildberries.

💰 <b>Ваш баланс:</b> {user.reports_balance} отчетов

Выберите действие ниже 👇
"""
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Сравнение карточек", callback_data="compare_cards")],
                [
                    InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
                    InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/wifftees")
                ],
                [InlineKeyboardButton(text="🔗 Реферальная ссылка", callback_data="referral_link")],
            ]
        )
    
    await message.answer(
        welcome_text,
        reply_markup=keyboard
    )


@router.callback_query(F.data == "referral_link")
async def referral_link_callback(callback: CallbackQuery, user: User):
    """Show user their referral link"""
    logger.info(f"User {user.id} requested referral link")

    await callback.answer()

    bot_info = await callback.bot.get_me()
    referral_url = f"https://t.me/{bot_info.username}?start={user.id}"

    await callback.message.answer(
        f"🔗 <b>Ваша реферальная ссылка:</b>\n\n"
        f"<code>{referral_url}</code>\n\n"
        f"Поделитесь этой ссылкой с друзьями — они смогут перейти в бота по вашей ссылке.",
    )
