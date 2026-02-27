"""Admin API handlers for conversions analytics, overview metrics, username listing, and broadcast.

These endpoints mirror the logic in ``bot/handlers/admin.py`` but expose it
over HTTP JSON for the Admin Mini App.  All routes live under
``/api/admin/*`` and rely on ``admin_auth_middleware`` for authentication.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Optional

from aiohttp import web

from api.admin_models import (
    BroadcastRequest,
    BroadcastResponse,
    ConversionGroup,
    ConversionStep,
    ConversionsRequest,
    ConversionsResponse,
    OverviewRequest,
    OverviewResponse,
    PriceRow,
    PricesListResponse,
    PricesUpdateRequest,
    PricesUpdateResponse,
    compute_range,
)
from bot.handlers.admin import CONVERSION_CATEGORIES
from database.dashboard_queries import (
    fetch_core_kpis,
    fetch_payer_segmentation,
    fetch_payment_metrics,
    fetch_referral_metrics,
    fetch_repeat_reporters,
)
from database.models import EventType
from database.models import Price, ProductOption
from database.queries import (
    bulk_upsert_prices,
    count_unique_users_by_events,
    get_all_prices,
    get_unique_user_ids_by_events,
    get_usernames_by_ids,
)

logger = logging.getLogger(__name__)


async def _resolve_count(source: list[EventType] | Callable) -> int:
    """Return user count for a conversion category source (all-time)."""
    if callable(source):
        return len(await source())
    return await count_unique_users_by_events(source)


async def _resolve_user_ids(source: list[EventType] | Callable) -> list[int]:
    """Return user IDs for a conversion category source (all-time)."""
    if callable(source):
        return await source()
    return await get_unique_user_ids_by_events(source)


async def _resolve_category_with_range(
    source: list[EventType] | Callable,
    range_start: Optional[datetime],
    range_end: datetime,
) -> tuple[list[int], bool]:
    """Resolve category to user IDs and whether range was applied.

    Returns:
        (user_ids, range_applied): range_applied is False for callable sources.
    """
    if callable(source):
        ids = await source()
        return ids, False
    ids = await get_unique_user_ids_by_events(
        source, range_start=range_start, range_end=range_end
    )
    return ids, True


async def overview_handler(request: web.Request) -> web.Response:
    """``POST /api/admin/overview``

    Request::

        { "range": "1d" | "7d" | "1m" | "all" }

    Response::

        {
          "range": "7d",
          "range_start": "2025-02-20T12:00:00+00:00",
          "range_end": "2025-02-27T12:00:00+00:00",
          "core_kpis": { ... },
          "payments": { ... },
          "referrals": { ... },
          "repeat_reporters": { ... },
          "payer_segmentation": { ... }
        }
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    try:
        req = OverviewRequest.model_validate(body)
    except Exception as e:
        return web.json_response(
            {"error": f"invalid request: {e}"},
            status=400,
        )

    tg_user = request.get("tg_user")
    logger.info(
        "[ADMIN-API] user=%s requested overview for range=%s",
        tg_user.id if tg_user else "?",
        req.range.value,
    )

    range_start, range_end = compute_range(req.range)
    logger.info(
        "[ADMIN-API] range_start=%s, range_end=%s",
        range_start,
        range_end,
    )

    core_kpis = await fetch_core_kpis(range_start, range_end)
    logger.info("[ADMIN-API] core_kpis=%s", core_kpis.model_dump())
    
    payments = await fetch_payment_metrics(range_start, range_end)
    logger.info("[ADMIN-API] payments=%s", payments.model_dump())
    
    referrals = await fetch_referral_metrics(range_start, range_end)
    logger.info("[ADMIN-API] referrals=%s", referrals.model_dump())
    
    repeat_reporters = await fetch_repeat_reporters()
    payer_segmentation = await fetch_payer_segmentation(range_start, range_end)

    resp = OverviewResponse(
        range=req.range,
        range_start=range_start,
        range_end=range_end,
        core_kpis=core_kpis,
        payments=payments,
        referrals=referrals,
        repeat_reporters=repeat_reporters,
        payer_segmentation=payer_segmentation,
    )

    return web.json_response(resp.model_dump(mode="json"))


async def conversions_handler(request: web.Request) -> web.Response:
    """``POST /api/admin/conversions``

    Request::

        { "range": "1d" | "7d" | "1m" | "all", "categories": [1, 3, 10] }

    Response::

        {
          "range": "7d",
          "range_start": "...",
          "range_end": "...",
          "groups": [
            { "category": 1, "size": 520, "range_applied": true },
            ...
          ],
          "conversions": [
            { "from_category": 1, "to_category": 3, "numerator": 180, "denominator": 520, "percent": 34.6 },
            ...
          ]
        }
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    try:
        req = ConversionsRequest.model_validate(body)
    except Exception as e:
        return web.json_response(
            {"error": f"invalid request: {e}"},
            status=400,
        )

    invalid = [c for c in req.categories if c not in CONVERSION_CATEGORIES]
    if invalid:
        max_num = max(CONVERSION_CATEGORIES)
        return web.json_response(
            {"error": f"invalid categories: {invalid}; valid range is 1–{max_num}"},
            status=400,
        )

    tg_user = request.get("tg_user")
    logger.info(
        "[ADMIN-API] user=%s requested conversions for categories %s range=%s",
        tg_user.id if tg_user else "?",
        req.categories,
        req.range.value,
    )

    range_start, range_end = compute_range(req.range)

    # Resolve each category to user IDs and range_applied
    id_sets: dict[int, set[int]] = {}
    range_applied: dict[int, bool] = {}
    for cat in req.categories:
        _label, source = CONVERSION_CATEGORIES[cat]
        ids, applied = await _resolve_category_with_range(
            source, range_start, range_end
        )
        id_sets[cat] = set(ids)
        range_applied[cat] = applied

    groups = [
        ConversionGroup(
            category=cat,
            size=len(id_sets[cat]),
            range_applied=range_applied[cat],
        )
        for cat in req.categories
    ]

    conversions: list[ConversionStep] = []
    for i in range(len(req.categories) - 1):
        from_cat, to_cat = req.categories[i], req.categories[i + 1]
        from_ids = id_sets[from_cat]
        to_ids = id_sets[to_cat]
        numerator = len(from_ids & to_ids)
        denominator = len(from_ids)
        percent = (numerator / denominator * 100) if denominator > 0 else None
        if percent is not None:
            percent = round(percent, 1)
        conversions.append(
            ConversionStep(
                from_category=from_cat,
                to_category=to_cat,
                numerator=numerator,
                denominator=denominator,
                percent=percent,
            )
        )

    resp = ConversionsResponse(
        range=req.range,
        range_start=range_start,
        range_end=range_end,
        groups=groups,
        conversions=conversions,
    )

    return web.json_response(resp.model_dump(mode="json"))


async def categories_handler(_request: web.Request) -> web.Response:
    """``GET /api/admin/categories``

    Response::

        {
          "categories": [
            { "category": 1, "label": "Зашли в бота" },
            { "category": 2, "label": "Нажали \"Баланс\"" },
            ...
          ]
        }
    """
    categories = [
        {"category": cat, "label": label}
        for cat, (label, _source) in sorted(CONVERSION_CATEGORIES.items())
    ]
    return web.json_response({"categories": categories})


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

    category: Optional[int] = body.get("category") if isinstance(body, dict) else None
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


async def broadcast_handler(request: web.Request) -> web.Response:
    """``POST /api/admin/broadcast``

    Request::

        { "category": 3, "message": "Hello" }

    Response::

        { "sent": 10, "failed": 0, "total": 10 }
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    try:
        req = BroadcastRequest.model_validate(body)
    except Exception as e:
        return web.json_response(
            {"error": f"invalid request: {e}"},
            status=400,
        )

    if req.category not in CONVERSION_CATEGORIES:
        max_num = max(CONVERSION_CATEGORIES)
        return web.json_response(
            {"error": f"invalid category: {req.category}; valid range is 1–{max_num}"},
            status=400,
        )

    tg_user = request.get("tg_user")
    logger.info(
        "[ADMIN-API] user=%s requested broadcast for category %d",
        tg_user.id if tg_user else "?",
        req.category,
    )

    _label, source = CONVERSION_CATEGORIES[req.category]
    user_ids = await _resolve_user_ids(source)

    bot = request.app.get("bot")
    if bot is None:
        logger.error("[ADMIN-API] bot not available in app state")
        return web.json_response(
            {"error": "server configuration error"},
            status=500,
        )

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=req.message)
            sent += 1
        except Exception as e:
            logger.warning("[ADMIN-API] failed to send to %s: %s", uid, e)
            failed += 1
        await asyncio.sleep(0.05)

    resp = BroadcastResponse(sent=sent, failed=failed, total=len(user_ids))
    return web.json_response(resp.model_dump())


async def prices_list_handler(_request: web.Request) -> web.Response:
    """``GET /api/admin/prices``

    Response::

        {
          "prices": [
            { "option": "SINGLE", "price": 100, "reports_amount": 1 },
            { "option": "PACKET", "price": 500, "reports_amount": 10 }
          ]
        }
    """
    prices = await get_all_prices()

    price_rows = [
        PriceRow(
            option=p.option.value,
            price=p.price,
            reports_amount=p.reports_amount,
        )
        for p in prices
    ]

    resp = PricesListResponse(prices=price_rows)
    return web.json_response(resp.model_dump())


async def prices_update_handler(request: web.Request) -> web.Response:
    """``POST /api/admin/prices``

    Request::

        {
          "prices": [
            { "option": "SINGLE", "price": 100, "reports_amount": 1 },
            { "option": "PACKET", "price": 500, "reports_amount": 10 }
          ]
        }

    Response::

        {
          "updated": 2,
          "prices": [
            { "option": "SINGLE", "price": 100, "reports_amount": 1 },
            { "option": "PACKET", "price": 500, "reports_amount": 10 }
          ]
        }
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    try:
        req = PricesUpdateRequest.model_validate(body)
    except Exception as e:
        return web.json_response(
            {"error": f"invalid request: {e}"},
            status=400,
        )

    tg_user = request.get("tg_user")
    logger.info(
        "[ADMIN-API] user=%s requested prices update for %d rows",
        tg_user.id if tg_user else "?",
        len(req.prices),
    )

    # Convert request rows to Price objects
    try:
        price_objects = [
            Price(
                option=ProductOption(row.option),
                price=row.price,
                reports_amount=row.reports_amount,
            )
            for row in req.prices
        ]
    except ValueError as e:
        return web.json_response(
            {"error": f"invalid product option: {e}"},
            status=400,
        )

    # Bulk upsert with validation
    try:
        updated_prices = await bulk_upsert_prices(price_objects)
    except ValueError as e:
        return web.json_response(
            {"error": f"validation failed: {e}"},
            status=400,
        )
    except Exception as e:
        logger.error("[ADMIN-API] failed to update prices: %s", e, exc_info=True)
        return web.json_response(
            {"error": "internal server error"},
            status=500,
        )

    # Convert back to response format
    price_rows = [
        PriceRow(
            option=p.option.value,
            price=p.price,
            reports_amount=p.reports_amount,
        )
        for p in updated_prices
    ]

    resp = PricesUpdateResponse(updated=len(price_rows), prices=price_rows)
    return web.json_response(resp.model_dump())
