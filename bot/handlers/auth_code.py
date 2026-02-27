"""Handler for authentication codes"""

import logging
from aiogram import Router, F
from aiogram.types import Message

from bot.config import settings

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text.regexp(r"^\d{4,6}$"))
async def handle_auth_code(message: Message, app):
    """
    Handler for SMS auth codes (4-6 digits).
    Only works for admin user.

    Args:
        message: Incoming message with code
        app: Application instance (injected from dispatcher)
    """

    logger.info("🔍 [AUTH_CODE] Handler triggered!")
    logger.info(f"🔍 [AUTH_CODE] Message text: '{message.text}'")
    logger.info(
        f"🔍 [AUTH_CODE] From user: {message.from_user.id} (@{message.from_user.username})"
    )
    logger.info(f"🔍 [AUTH_CODE] Expected admin: {settings.admin_telegram_id}")

    # Check if sender is admin
    if message.from_user.id != settings.admin_telegram_id:
        logger.warning(
            f"⚠️ [AUTH_CODE] User {message.from_user.id} is not admin {settings.admin_telegram_id}"
        )
        return  # Ignore non-admin users

    logger.info("✅ [AUTH_CODE] Admin verified!")

    # Check if there's a pending auth request
    logger.info(f"🔍 [AUTH_CODE] Checking app object: {app}")
    wb_client = getattr(app, "wb_client", None)
    logger.info(f"🔍 [AUTH_CODE] WBClient: {wb_client}")

    if not wb_client:
        logger.error("❌ [AUTH_CODE] WBClient not found in app")
        await message.answer("❌ Ошибка: WBClient не найден")
        return

    auth_service = getattr(wb_client, "_auth_service", None)
    logger.info(f"🔍 [AUTH_CODE] AuthService: {auth_service}")

    if not auth_service:
        logger.error("❌ [AUTH_CODE] AuthService not found in WBClient")
        await message.answer("❌ Ошибка: AuthService не найден")
        return

    pending_code = getattr(auth_service, "_pending_code_future", None)
    logger.info(f"🔍 [AUTH_CODE] Pending code future: {pending_code}")
    logger.info(
        f"🔍 [AUTH_CODE] Future done: {pending_code.done() if pending_code else 'N/A'}"
    )

    if not pending_code or pending_code.done():
        logger.warning("⚠️ [AUTH_CODE] No active auth request")
        await message.answer(
            "❌ <b>Нет активного запроса на код</b>\n\n"
            "Возможно, запрос уже обработан или истёк."
        )
        return

    # Send code to the waiting future
    code = message.text.strip()
    logger.info(f"📤 [AUTH_CODE] Setting code result: '{code}'")

    try:
        pending_code.set_result(code)
        logger.info(
            f"✅ [AUTH_CODE] Auth code delivered successfully: {len(code)} digits"
        )

        await message.answer("✅ <b>Код принят!</b>\n\nВыполняется авторизация...")
    except Exception as e:
        logger.error(f"❌ [AUTH_CODE] Error setting result: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {e}")
