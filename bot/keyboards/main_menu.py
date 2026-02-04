"""Main menu keyboards"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Сравнение карточек")],
            [KeyboardButton(text="💰 Баланс")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard
