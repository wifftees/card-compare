"""Balance handler"""
import logging
from aiogram import Router, F
from aiogram.types import Message

from database.models import User

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "💰 Баланс")
async def show_balance(message: Message, user: User):
    """Show user balance"""
    logger.info(f"User {user.id} requested balance")
    
    balance_text = f"""
💰 <b>Ваш баланс</b>

Доступно отчетов: <b>{user.reports_balance}</b>

Для пополнения баланса обратитесь к администратору.
"""
    
    await message.answer(balance_text)
