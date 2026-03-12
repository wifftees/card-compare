"""Inline keyboards for notification campaigns."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


CAMPAIGN_KEYBOARDS: dict[str, InlineKeyboardMarkup] = {
    "click_start_no_report": InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Пример отчета", callback_data="show_example_report"
                )
            ]
        ]
    ),
    "click_example_report": InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Купить 1 отчет",
                    callback_data="buy:SINGLE",
                )
            ]
        ]
    ),
    "generated_report": InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Купить 1 отчет",
                    callback_data="buy:SINGLE",
                )
            ]
        ]
    ),
}


def get_campaign_keyboard(campaign_id: str) -> InlineKeyboardMarkup | None:
    """Return an inline keyboard for a notification campaign, if configured."""
    return CAMPAIGN_KEYBOARDS.get(campaign_id)
