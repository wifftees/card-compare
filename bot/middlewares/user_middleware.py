"""User middleware for automatic user creation"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from database.queries import get_or_create_user
from database.models import User

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    """Middleware to ensure user exists in database"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Process event and ensure user exists"""
        
        # Get Telegram user from event
        tg_user: TgUser = data.get("event_from_user")
        
        if not tg_user:
            logger.warning("No user in event, skipping middleware")
            return await handler(event, data)
        
        try:
            # Get or create user in database
            user = await get_or_create_user(
                user_id=tg_user.id,
                username=tg_user.username
            )
            
            if user:
                # Add user to handler data
                data["user"] = user
                logger.debug(f"User {tg_user.id} loaded (balance: {user.reports_balance})")
            else:
                logger.error(f"Failed to get/create user {tg_user.id}")
                # Don't call handler if user creation failed
                return None
        except Exception as e:
            logger.error(f"Error in user middleware for user {tg_user.id}: {e}", exc_info=True)
            # Don't call handler if there was an error
            return None
        
        return await handler(event, data)
