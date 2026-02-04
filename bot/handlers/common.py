"""Common handlers for unmatched messages"""
import logging
from aiogram import Router
from aiogram.types import Message

from bot.keyboards.main_menu import get_main_menu_keyboard
from database.models import User

logger = logging.getLogger(__name__)

router = Router()


@router.message()
async def handle_unknown_message(message: Message, user: User):
    """Catch-all handler for unmatched messages"""
    logger.info(f"User {user.id} sent unmatched message: {message.text}")
    
    await message.answer(
        "❓ Не понимаю эту команду.\n\n"
        "Используйте кнопки меню ниже 👇",
        reply_markup=get_main_menu_keyboard()
    )
