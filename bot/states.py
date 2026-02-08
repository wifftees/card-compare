"""FSM states for bot"""
from aiogram.fsm.state import State, StatesGroup


class RefillBalanceStates(StatesGroup):
    """States for refilling balance"""
    waiting_for_payment = State()


class CompareCardsStates(StatesGroup):
    """States for comparing cards"""
    waiting_for_articles = State()
    processing_report = State()


class AdminStates(StatesGroup):
    """States for admin broadcast flow"""
    choosing_group = State()      # Selecting user segment
    entering_message = State()    # Typing broadcast message
    confirming_message = State()  # Confirming before send
