"""Common handlers for unmatched messages"""
import logging
from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from database.models import User

logger = logging.getLogger(__name__)

router = Router()


@router.message()
async def handle_unknown_message(message: Message, user: User):
    """Catch-all handler for unmatched messages"""
    logger.info(f"User {user.id} sent unmatched message: {message.text}")
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Сравнение карточек", callback_data="compare_cards")],
            [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
        ]
    )
    
    await message.answer(
        "❓ Не понимаю эту команду.\n\n"
        "Используйте кнопки меню ниже 👇",
        reply_markup=keyboard
    )
