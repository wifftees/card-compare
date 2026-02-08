"""Loading sticker utilities for indicating processing state"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiogram import Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)

# Animated loading sticker ID
LOADING_STICKER_ID = "CAACAgIAAxkBAAEVqDFpf0pGFIP-sRsnvOx-jWd1idNYOwACtCMAAphLKUjeub7NKlvk2TgE"


async def send_loading_sticker(message: Message) -> int:
    """
    Send an animated loading sticker to indicate processing.
    
    Args:
        message: The message to reply to with the sticker
        
    Returns:
        int: Message ID of the sent sticker (for later deletion)
    """
    sticker_msg = await message.answer_sticker(sticker=LOADING_STICKER_ID)
    logger.debug(f"📤 Sent loading sticker {sticker_msg.message_id}")
    return sticker_msg.message_id


async def delete_loading_sticker(
    bot: Bot,
    chat_id: int,
    message_id: int | None,
    *,
    silent: bool = True
) -> bool:
    """
    Delete a loading sticker message.
    
    Args:
        bot: The bot instance
        chat_id: Chat ID where the sticker was sent
        message_id: Message ID of the sticker to delete
        silent: If True, suppress errors (default). If False, raise exceptions.
        
    Returns:
        bool: True if deleted successfully, False otherwise
    """
    if not message_id:
        return False
    
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"🗑️  Deleted loading sticker {message_id}")
        return True
    except Exception as e:
        if silent:
            logger.warning(f"⚠️  Could not delete loading sticker: {e}")
            return False
        raise


@asynccontextmanager
async def LoadingSticker(
    message: Message,
    bot: Bot | None = None,
    *,
    auto_delete: bool = True
) -> AsyncGenerator[int, None]:
    """
    Context manager for showing a loading sticker during an operation.
    
    Usage:
        async with LoadingSticker(message, bot) as sticker_id:
            # Do long-running operation
            await process_something()
        # Sticker is automatically deleted
        
    For queue-based operations where deletion happens later:
        async with LoadingSticker(message, auto_delete=False) as sticker_id:
            task = ReportTask.create(..., loading_message_id=sticker_id)
            await queue.add_task(task)
        # Sticker will NOT be deleted - handle it manually later
    
    Args:
        message: The message to reply to with the sticker
        bot: Bot instance for deletion. Required if auto_delete=True.
        auto_delete: Whether to automatically delete the sticker on exit (default: True)
        
    Yields:
        int: Message ID of the loading sticker
        
    Raises:
        ValueError: If auto_delete=True but no bot instance provided
    """
    if auto_delete and bot is None:
        raise ValueError("Bot instance required when auto_delete=True")
    
    sticker_msg_id = await send_loading_sticker(message)
    
    try:
        yield sticker_msg_id
    finally:
        if auto_delete and bot:
            await delete_loading_sticker(bot, message.chat.id, sticker_msg_id)
