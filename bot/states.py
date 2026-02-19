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
    main_menu = State()           # Main admin menu
    choosing_action = State()     # Choosing between conversions or broadcast
    choosing_group = State()      # Selecting user segment
    entering_message = State()    # Typing broadcast message
    confirming_message = State()  # Confirming before send
    waiting_for_conversion_categories = State()  # Waiting for conversion category numbers
    waiting_for_usernames_category = State()      # Waiting for a single category number to list usernames
