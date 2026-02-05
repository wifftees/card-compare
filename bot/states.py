"""FSM states for bot"""
from aiogram.fsm.state import State, StatesGroup


class RefillBalanceStates(StatesGroup):
    """States for refilling balance"""
    waiting_for_amount = State()
    waiting_for_confirmation = State()
    waiting_for_payment = State()
