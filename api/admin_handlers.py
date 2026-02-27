"""Admin API handlers for conversions analytics and username listing.

These endpoints mirror the logic in ``bot/handlers/admin.py`` but expose it
over HTTP JSON for the Admin Mini App.  Both routes live under
``/api/admin/*`` and rely on ``admin_auth_middleware`` for authentication.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from aiohttp import web

from bot.handlers.admin import CONVERSION_CATEGORIES
from database.models import EventType
from database.queries import (
    count_unique_users_by_events,
    get_unique_user_ids_by_events,
    get_usernames_by_ids,
)

logger = logging.getLogger(__name__)


async def _resolve_count(source: list[EventType] | Callable) -> int:
    """Return user count for a conversion category source."""
    if callable(source):
        return len(await source())
    return await count_unique_users_by_events(source)


async def _resolve_user_ids(source: list[EventType] | Callable) -> list[int]:
    """Return user IDs for a conversion category source."""
    if callable(source):
        return await source()
    return await get_unique_user_ids_by_events(source)


async def conversions_handler(request: web.Request) -> web.Response:
    """``POST /api/admin/conversions``

    Request::

        { "categories": [1, 3, 10] }

    Response::

        {
          "steps": [
            { "category": 1, "label": "Зашли в бота", "count": 520 },
            { "category": 3, "label": "Нажали \"Сравнить карточки\"", "count": 180 },
            { "category": 10, "label": "Сделали покупку", "count": 34 }
          ],
          "conversions": [
            { "from": 1, "to": 3, "percentage": 34.6 },
            { "from": 3, "to": 10, "percentage": 18.9 }
          ]
        }
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    categories: list[int] | None = body.get("categories") if isinstance(body, dict) else None
    if not categories or not isinstance(categories, list):
        return web.json_response(
            {"error": "\"categories\" must be a non-empty list of ints"},
            status=400,
        )

    seen: set[int] = set()
    for cat in categories:
        if not isinstance(cat, int):
            return web.json_response(
                {"error": f"category value must be int, got {type(cat).__name__}"},
                status=400,
            )
        if cat in seen:
            return web.json_response(
                {"error": f"duplicate category: {cat}"},
                status=400,
            )
        seen.add(cat)

    invalid = [c for c in categories if c not in CONVERSION_CATEGORIES]
    if invalid:
        max_num = max(CONVERSION_CATEGORIES)
        return web.json_response(
            {"error": f"invalid categories: {invalid}; valid range is 1–{max_num}"},
            status=400,
        )

    tg_user = request.get("tg_user")
    logger.info(
        "[ADMIN-API] user=%s requested conversions for categories %s",
        tg_user.id if tg_user else "?",
        categories,
    )

    counts: dict[int, int] = {}
    for cat in categories:
        _label, source = CONVERSION_CATEGORIES[cat]
        counts[cat] = await _resolve_count(source)

    steps = [
        {
            "category": cat,
            "label": CONVERSION_CATEGORIES[cat][0],
            "count": counts[cat],
        }
        for cat in categories
    ]

    conversions: list[dict] = []
    for i in range(len(categories) - 1):
        a, b = categories[i], categories[i + 1]
        count_a, count_b = counts[a], counts[b]
        if count_a > 0:
            pct = round(count_b / count_a * 100, 1)
        else:
            pct = None
        conversions.append({"from": a, "to": b, "percentage": pct})

    return web.json_response({"steps": steps, "conversions": conversions})


async def usernames_handler(request: web.Request) -> web.Response:
    """``POST /api/admin/usernames``

    Request::

        { "category": 5 }

    Response::

        {
          "category": 5,
          "label": "Выбрали опцию \"Один отчет\"",
          "total": 3,
          "users": [
            { "user_id": 111, "username": "alice" },
            { "user_id": 222, "username": null }
          ]
        }
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    category: int | None = body.get("category") if isinstance(body, dict) else None
    if category is None or not isinstance(category, int):
        return web.json_response(
            {"error": "\"category\" must be an int"},
            status=400,
        )

    if category not in CONVERSION_CATEGORIES:
        max_num = max(CONVERSION_CATEGORIES)
        return web.json_response(
            {"error": f"invalid category: {category}; valid range is 1–{max_num}"},
            status=400,
        )

    tg_user = request.get("tg_user")
    logger.info(
        "[ADMIN-API] user=%s requested usernames for category %d",
        tg_user.id if tg_user else "?",
        category,
    )

    label, source = CONVERSION_CATEGORIES[category]
    user_ids = await _resolve_user_ids(source)

    if not user_ids:
        return web.json_response({
            "category": category,
            "label": label,
            "total": 0,
            "users": [],
        })

    usernames_map = await get_usernames_by_ids(user_ids)

    users = [
        {"user_id": uid, "username": usernames_map.get(uid)}
        for uid in user_ids
    ]

    return web.json_response({
        "category": category,
        "label": label,
        "total": len(users),
        "users": users,
    })
