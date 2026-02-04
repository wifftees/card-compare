"""Start command handler"""
import logging
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.main_menu import get_main_menu_keyboard
from database.models import User

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    """Handle /start command"""
    logger.info(f"User {user.id} started the bot")
    
    welcome_text = f"""
👋 Привет, {message.from_user.first_name}!

Я бот для генерации отчетов Wildberries.

📊 <b>Доступные функции:</b>
• Фильтрованные отчеты - полный анализ по периодам и сегментам
• Сравнение карточек - сравнение товаров по артикулам

💰 <b>Ваш баланс:</b> {user.reports_balance} отчетов

Выберите действие на клавиатуре ниже 👇
"""
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard()
    )
