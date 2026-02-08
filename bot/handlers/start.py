"""Start command handler"""
import logging
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from database.models import User, EventType, CreateEventDTO
from database.queries import create_event

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    """Handle /start command"""
    logger.info(f"User {user.id} started the bot")
    
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
        ]
    )
    
    await message.answer(
        welcome_text,
        reply_markup=keyboard
    )
