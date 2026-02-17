"""Status message utilities for indicating report generation progress"""
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)

TOTAL_STAGES = 14


@dataclass(frozen=True)
class Stage:
    """Definition of a single processing stage"""
    emoji: str
    description: str


STAGES: dict[int, Stage] = {
    1: Stage(emoji="", description="Открываем страницу сравнения..."),
    2: Stage(emoji="", description="Вводим артикулы товаров..."),
    3: Stage(emoji="", description="Проверяем добавленные карточки..."),
    4: Stage(emoji="", description="Запускаем сравнение карточек..."),
    5: Stage(emoji="", description="Применяем фильтры отчетов..."),
    6: Stage(emoji="", description="Обрабатываем период: Сегодня..."),
    7: Stage(emoji="", description="Обрабатываем период: Неделя..."),
    8: Stage(emoji="", description="Обрабатываем период: Месяц..."),
    9: Stage(emoji="", description="Обрабатываем период: Квартал..."),
    10: Stage(emoji="", description="Открываем менеджер загрузок..."),
    11: Stage(emoji="", description="Ожидаем готовности документов..."),
    12: Stage(emoji="", description="Скачиваем документы..."),
    13: Stage(emoji="", description="Упаковываем архив..."),
    14: Stage(emoji="", description="Завершение..."),
}


def format_status_text(stage: int) -> str:
    """
    Build the formatted HTML message for a given stage number.

    Shows a progress bar and percentage alongside the current stage description.

    Args:
        stage: Stage number (1-based, must be in STAGES)

    Returns:
        str: Formatted HTML text ready to be sent/edited
    """
    info = STAGES[stage]
    filled = "▓" * stage
    empty = "░" * (TOTAL_STAGES - stage)
    percent = int(stage / TOTAL_STAGES * 100)
    return (
        f"⏳ <b>Генерация отчета</b>\n\n"
        f"{info.emoji} {info.description}\n\n"
        f"<code>{filled}{empty}</code> {percent}%"
    )


async def send_status_message(message: Message) -> int:
    """
    Send the initial status message (stage 1) to the user.

    Args:
        message: The user message to reply to

    Returns:
        int: Message ID of the sent status message (for later editing/deletion)
    """
    text = format_status_text(stage=1)
    status_msg = await message.answer(text)
    logger.debug(f"📤 Sent status message {status_msg.message_id}")
    return status_msg.message_id


async def update_status_message(
    bot: Bot,
    chat_id: int,
    message_id: int | None,
    stage: int,
) -> bool:
    """
    Edit the status message to reflect the current processing stage.

    Failures are silently caught so they never abort report generation.

    Args:
        bot: The bot instance
        chat_id: Chat ID where the status message was sent
        message_id: Message ID of the status message to edit
        stage: Stage number to display (1-based, must be in STAGES)

    Returns:
        bool: True if edited successfully, False otherwise
    """
    if not message_id:
        return False

    try:
        text = format_status_text(stage)
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
        )
        logger.info(f"✏️  Updated status message {message_id} to stage {stage}")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Could not update status message: {e}")
        return False


async def delete_status_message(
    bot: Bot,
    chat_id: int,
    message_id: int | None,
    *,
    silent: bool = True,
) -> bool:
    """
    Delete a status message.

    Args:
        bot: The bot instance
        chat_id: Chat ID where the status message was sent
        message_id: Message ID of the status message to delete
        silent: If True, suppress errors (default). If False, raise exceptions.

    Returns:
        bool: True if deleted successfully, False otherwise
    """
    if not message_id:
        return False

    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"🗑️  Deleted status message {message_id}")
        return True
    except Exception as e:
        if silent:
            logger.warning(f"⚠️  Could not delete status message: {e}")
            return False
        raise
