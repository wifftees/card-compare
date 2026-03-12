"""aiohttp middleware that gates ``/api/admin/*`` behind Telegram WebApp auth.

Usage::

    from api.admin_auth import admin_auth_middleware

    app = web.Application(middlewares=[admin_auth_middleware])

The middleware:

1. Passes through requests whose path does NOT start with ``/api/admin/``.
2. Reads the ``X-Telegram-Init-Data`` header — **401** if absent.
3. Verifies the HMAC-SHA256 signature — **401** if invalid.
4. Extracts ``user.id`` and checks ``settings.admin_id_list`` — **403** if not admin.
5. Stores the verified ``TelegramWebAppUser`` in ``request["tg_user"]`` for handlers.
"""

from __future__ import annotations

import logging

from aiohttp import web

from api.telegram_auth import extract_user, verify_init_data
from bot.config import settings

logger = logging.getLogger(__name__)

_ADMIN_PATH_PREFIX = "/api/admin/"
_INIT_DATA_HEADER = "X-Telegram-Init-Data"


@web.middleware
async def admin_auth_middleware(
    request: web.Request,
    handler: web.RequestHandler,
) -> web.StreamResponse:
    """Enforce Telegram WebApp auth + admin allowlist on admin routes."""
    if not request.path.startswith(_ADMIN_PATH_PREFIX):
        return await handler(request)  # type: ignore[operator]

    raw_init_data = request.headers.get(_INIT_DATA_HEADER)
    if not raw_init_data:
        logger.debug("Missing %s header for %s", _INIT_DATA_HEADER, request.path)
        return web.json_response({"error": "missing initData"}, status=401)

    bot_token = settings.bot_token
    if not verify_init_data(raw_init_data, bot_token):
        logger.warning("Invalid initData signature for %s", request.path)
        return web.json_response({"error": "invalid initData"}, status=401)

    user = extract_user(raw_init_data)
    if user is None:
        logger.warning("Could not extract user from initData for %s", request.path)
        return web.json_response({"error": "invalid initData"}, status=401)

    if user.id not in settings.admin_id_list:
        logger.warning(
            "Non-admin user %d attempted access to %s", user.id, request.path
        )
        return web.json_response({"error": "forbidden"}, status=403)

    request["tg_user"] = user
    return await handler(request)  # type: ignore[operator]
