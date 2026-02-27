"""Tests for admin API handlers.

Covers:
- Task 6.2: POST /api/admin/overview auth behavior (401/403)
- Task 6.3: POST /api/admin/overview response shape and computed fields
- Task 6.4: POST /api/admin/conversions group sizing and conversion math
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient

from api.admin_handlers import (
    broadcast_handler,
    conversions_handler,
    overview_handler,
    prices_list_handler,
    prices_update_handler,
)
from database.models import EventType, Price, ProductOption
from api.admin_models import (
    CoreKPIs,
    PayerSegmentation,
    PaymentMetrics,
    ReferralFunnel,
    ReferralMetrics,
    ReferrerEntry,
    RepeatReporters,
    RevenueReferrerEntry,
)
from api.telegram_auth import TelegramWebAppUser

BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------


def _build_init_data(
    params: dict[str, str],
    bot_token: str = BOT_TOKEN,
    *,
    tamper_hash: str | None = None,
) -> str:
    """Build a properly signed initData string."""
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    final_hash = tamper_hash if tamper_hash is not None else computed_hash
    return urlencode({**params, "hash": final_hash})


def _make_user_json(user_id: int = 12345, **extra: Any) -> str:
    data: dict[str, object] = {"id": user_id, "first_name": "Test", **extra}
    return json.dumps(data)


@pytest.fixture
def admin_init_data() -> str:
    """Valid initData for admin user (ID 111)."""
    params = {"auth_date": "1700000000", "user": _make_user_json(user_id=111)}
    return _build_init_data(params)


@pytest.fixture
def non_admin_init_data() -> str:
    """Valid initData for non-admin user (ID 999)."""
    params = {"auth_date": "1700000000", "user": _make_user_json(user_id=999)}
    return _build_init_data(params)


def _make_admin_app(
    include_broadcast: bool = False, include_prices: bool = False
) -> web.Application:
    """Create test app with admin auth middleware."""
    from api.admin_auth import admin_auth_middleware

    app = web.Application(middlewares=[admin_auth_middleware])
    app.router.add_post("/api/admin/overview", overview_handler)
    app.router.add_post("/api/admin/conversions", conversions_handler)
    if include_broadcast:
        app["bot"] = AsyncMock()
        app.router.add_post("/api/admin/broadcast", broadcast_handler)
    if include_prices:
        app.router.add_get("/api/admin/prices", prices_list_handler)
        app.router.add_post("/api/admin/prices", prices_update_handler)
    return app


_MOCK_SETTINGS = type(
    "MockSettings",
    (),
    {"bot_token": BOT_TOKEN, "admin_id_list": [111]},
)()


# ---------------------------------------------------------------------------
# Task 6.2: Auth behavior tests for POST /api/admin/overview
# ---------------------------------------------------------------------------


class TestOverviewAuth:
    """Test auth behavior: missing/invalid initData → 401; non-admin → 403."""

    @pytest.mark.asyncio
    async def test_missing_init_data_returns_401(self, aiohttp_client: Any) -> None:
        """Missing X-Telegram-Init-Data header should return 401."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            
            resp = await client.post(
                "/api/admin/overview",
                json={"range": "1d"},
            )
        
        assert resp.status == 401
        body = await resp.json()
        assert "error" in body
        assert "initdata" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Invalid initData signature should return 401."""
        tampered = admin_init_data[:-8] + "00000000"
        
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            
            resp = await client.post(
                "/api/admin/overview",
                json={"range": "1d"},
                headers={"X-Telegram-Init-Data": tampered},
            )
        
        assert resp.status == 401
        body = await resp.json()
        assert "error" in body

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(
        self, aiohttp_client: Any, non_admin_init_data: str
    ) -> None:
        """Valid initData for non-admin user should return 403."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            
            resp = await client.post(
                "/api/admin/overview",
                json={"range": "1d"},
                headers={"X-Telegram-Init-Data": non_admin_init_data},
            )
        
        assert resp.status == 403
        body = await resp.json()
        assert "error" in body
        assert "forbidden" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_malformed_json_body_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Malformed JSON should return 400."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            
            resp = await client.post(
                "/api/admin/overview",
                data="not-json",
                headers={
                    "X-Telegram-Init-Data": admin_init_data,
                    "Content-Type": "application/json",
                },
            )
        
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_invalid_range_preset_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Invalid range preset should return 400."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            
            resp = await client.post(
                "/api/admin/overview",
                json={"range": "invalid"},
                headers={"X-Telegram-Init-Data": admin_init_data},
            )
        
        assert resp.status == 400
        body = await resp.json()
        assert "error" in body


# ---------------------------------------------------------------------------
# Task 6.3: Response shape and computed fields for POST /api/admin/overview
# ---------------------------------------------------------------------------


class TestOverviewResponse:
    """Test response shape and key computed fields with controlled fixtures."""

    @pytest.mark.asyncio
    async def test_overview_response_shape(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Overview response should have all required sections."""
        mock_core_kpis = CoreKPIs(
            new_users=10,
            active_users=8,
            reports_generated=25,
        )
        mock_payments = PaymentMetrics(
            revenue=5000,
            paying_users=3,
            by_status={"success": 3, "pending": 1},
            revenue_by_option={"one_report": 2000, "unlimited": 3000},
        )
        mock_referrals = ReferralMetrics(
            active_referrers=2,
            new_referred_users=5,
            referrals_per_referrer_avg=2.5,
            referrals_per_referrer_median=2.0,
            top_referrers_by_referred_users=[
                ReferrerEntry(user_id=100, count=3),
                ReferrerEntry(user_id=200, count=2),
            ],
            qualified_referrals_count=4,
            qualified_referrals_rate=0.8,
            referred_revenue=1500,
            top_referrers_by_referred_revenue=[
                RevenueReferrerEntry(user_id=100, revenue=1000),
            ],
            referral_funnel=ReferralFunnel(created=5, activated=4, paid=2),
            estimated_bonus_earned=300,
        )
        mock_repeat_reporters = RepeatReporters(
            repeat_reporters_count=3,
            repeat_reporters_rate=0.3,
        )
        mock_payer_segmentation = PayerSegmentation(
            new_payer_count=2,
            returning_payer_count=1,
            churned_payer_count=0,
            one_time_payer_count=1,
            repeat_payer_count=1,
            power_payer_count=1,
        )
        
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch("api.admin_handlers.fetch_core_kpis", return_value=mock_core_kpis):
                with patch("api.admin_handlers.fetch_payment_metrics", return_value=mock_payments):
                    with patch("api.admin_handlers.fetch_referral_metrics", return_value=mock_referrals):
                        with patch("api.admin_handlers.fetch_repeat_reporters", return_value=mock_repeat_reporters):
                            with patch("api.admin_handlers.fetch_payer_segmentation", return_value=mock_payer_segmentation):
                                app = _make_admin_app()
                                client: TestClient = await aiohttp_client(app)
                                
                                resp = await client.post(
                                    "/api/admin/overview",
                                    json={"range": "7d"},
                                    headers={"X-Telegram-Init-Data": admin_init_data},
                                )
        
        assert resp.status == 200
        body = await resp.json()
        
        # Verify top-level structure
        assert "range" in body
        assert body["range"] == "7d"
        assert "range_start" in body
        assert "range_end" in body
        assert "core_kpis" in body
        assert "payments" in body
        assert "referrals" in body
        assert "repeat_reporters" in body
        assert "payer_segmentation" in body
        
        # Verify core_kpis section
        assert body["core_kpis"]["new_users"] == 10
        assert body["core_kpis"]["active_users"] == 8
        assert body["core_kpis"]["reports_generated"] == 25
        
        # Verify payments section
        assert body["payments"]["revenue"] == 5000
        assert body["payments"]["paying_users"] == 3
        assert "by_status" in body["payments"]
        assert "revenue_by_option" in body["payments"]
        
        # Verify referrals section
        assert body["referrals"]["active_referrers"] == 2
        assert body["referrals"]["new_referred_users"] == 5
        assert body["referrals"]["qualified_referrals_count"] == 4
        assert body["referrals"]["qualified_referrals_rate"] == 0.8
        assert len(body["referrals"]["top_referrers_by_referred_users"]) == 2
        
        # Verify repeat_reporters section
        assert body["repeat_reporters"]["repeat_reporters_count"] == 3
        assert body["repeat_reporters"]["repeat_reporters_rate"] == 0.3
        
        # Verify payer_segmentation section
        assert body["payer_segmentation"]["new_payer_count"] == 2
        assert body["payer_segmentation"]["one_time_payer_count"] == 1

    @pytest.mark.asyncio
    async def test_overview_range_metadata(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Range metadata should be correctly populated."""
        mock_core_kpis = CoreKPIs(new_users=0, active_users=0, reports_generated=0)
        mock_payments = PaymentMetrics(
            revenue=0, paying_users=0, by_status={}, revenue_by_option={}
        )
        mock_referrals = ReferralMetrics(
            active_referrers=0,
            new_referred_users=0,
            referrals_per_referrer_avg=None,
            referrals_per_referrer_median=None,
            top_referrers_by_referred_users=[],
            qualified_referrals_count=0,
            qualified_referrals_rate=None,
            referred_revenue=0,
            top_referrers_by_referred_revenue=[],
            referral_funnel=ReferralFunnel(created=0, activated=0, paid=0),
            estimated_bonus_earned=0,
        )
        mock_repeat_reporters = RepeatReporters(
            repeat_reporters_count=0, repeat_reporters_rate=None
        )
        mock_payer_segmentation = PayerSegmentation(
            new_payer_count=0,
            returning_payer_count=0,
            churned_payer_count=0,
            one_time_payer_count=0,
            repeat_payer_count=0,
            power_payer_count=0,
        )
        
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch("api.admin_handlers.fetch_core_kpis", return_value=mock_core_kpis):
                with patch("api.admin_handlers.fetch_payment_metrics", return_value=mock_payments):
                    with patch("api.admin_handlers.fetch_referral_metrics", return_value=mock_referrals):
                        with patch("api.admin_handlers.fetch_repeat_reporters", return_value=mock_repeat_reporters):
                            with patch("api.admin_handlers.fetch_payer_segmentation", return_value=mock_payer_segmentation):
                                app = _make_admin_app()
                                client: TestClient = await aiohttp_client(app)
                                
                                resp = await client.post(
                                    "/api/admin/overview",
                                    json={"range": "all"},
                                    headers={"X-Telegram-Init-Data": admin_init_data},
                                )
        
        assert resp.status == 200
        body = await resp.json()
        
        assert body["range"] == "all"
        assert body["range_start"] is None  # "all" preset has no start
        assert body["range_end"] is not None
        
        # Verify range_end is a valid ISO datetime (handle 'Z' suffix for Python 3.9)
        range_end_str = body["range_end"].replace("Z", "+00:00")
        range_end = datetime.fromisoformat(range_end_str)
        assert range_end.tzinfo is not None


# ---------------------------------------------------------------------------
# Task 6.4: Group sizing and adjacent conversion math
# ---------------------------------------------------------------------------


class TestConversionsHandler:
    """Test group sizing and adjacent conversion computation."""

    @pytest.mark.asyncio
    async def test_conversions_group_sizing(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Groups should report correct sizes and range_applied flag."""
        # Mock CONVERSION_CATEGORIES
        mock_categories = {
            1: ("Started bot", []),
            2: ("Clicked compare", []),
            3: ("Generated report", []),
        }
        
        # Mock resolution functions
        async def mock_resolve(source: Any, range_start: Any, range_end: Any) -> tuple[list[int], bool]:
            # Simulate event-based (range_applied=True) vs callable (range_applied=False)
            if callable(source):
                return [1, 2, 3], False
            return [1, 2, 3, 4, 5], True
        
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch("api.admin_handlers.CONVERSION_CATEGORIES", mock_categories):
                with patch("api.admin_handlers._resolve_category_with_range", side_effect=mock_resolve):
                    app = _make_admin_app()
                    client: TestClient = await aiohttp_client(app)
                    
                    resp = await client.post(
                        "/api/admin/conversions",
                        json={"range": "7d", "categories": [1, 2, 3]},
                        headers={"X-Telegram-Init-Data": admin_init_data},
                    )
        
        assert resp.status == 200
        body = await resp.json()
        
        assert "groups" in body
        assert len(body["groups"]) == 3
        
        for group in body["groups"]:
            assert "category" in group
            assert "size" in group
            assert "range_applied" in group
            assert isinstance(group["size"], int)
            assert isinstance(group["range_applied"], bool)

    @pytest.mark.asyncio
    async def test_conversions_adjacent_math(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Adjacent conversions should compute numerator/denominator/percent correctly."""
        mock_categories = {
            1: ("Group A", []),
            2: ("Group B", []),
            3: ("Group C", []),
        }
        
        # Define specific user sets for each category
        call_count = 0
        async def mock_resolve(source: Any, range_start: Any, range_end: Any) -> tuple[list[int], bool]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Category 1: 10 users
                return list(range(1, 11)), True
            elif call_count == 2:  # Category 2: 6 users (overlap with 1)
                return list(range(1, 7)), True
            else:  # Category 3: 3 users (overlap with 2)
                return list(range(1, 4)), True
        
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch("api.admin_handlers.CONVERSION_CATEGORIES", mock_categories):
                with patch("api.admin_handlers._resolve_category_with_range", side_effect=mock_resolve):
                    app = _make_admin_app()
                    client: TestClient = await aiohttp_client(app)
                    
                    resp = await client.post(
                        "/api/admin/conversions",
                        json={"range": "1d", "categories": [1, 2, 3]},
                        headers={"X-Telegram-Init-Data": admin_init_data},
                    )
        
        assert resp.status == 200
        body = await resp.json()
        
        assert "conversions" in body
        assert len(body["conversions"]) == 2  # 3 categories → 2 adjacent pairs
        
        # First conversion: 1→2
        conv1 = body["conversions"][0]
        assert conv1["from_category"] == 1
        assert conv1["to_category"] == 2
        assert conv1["numerator"] == 6  # Users in both 1 and 2
        assert conv1["denominator"] == 10  # Users in 1
        assert conv1["percent"] == 60.0  # 6/10 * 100
        
        # Second conversion: 2→3
        conv2 = body["conversions"][1]
        assert conv2["from_category"] == 2
        assert conv2["to_category"] == 3
        assert conv2["numerator"] == 3  # Users in both 2 and 3
        assert conv2["denominator"] == 6  # Users in 2
        assert conv2["percent"] == 50.0  # 3/6 * 100

    @pytest.mark.asyncio
    async def test_conversions_denominator_zero_returns_null_percent(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """When denominator is 0, percent should be null."""
        mock_categories = {
            1: ("Empty group", []),
            2: ("Another group", []),
        }
        
        call_count = 0
        async def mock_resolve(source: Any, range_start: Any, range_end: Any) -> tuple[list[int], bool]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Category 1: 0 users
                return [], True
            else:  # Category 2: 5 users
                return [1, 2, 3, 4, 5], True
        
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch("api.admin_handlers.CONVERSION_CATEGORIES", mock_categories):
                with patch("api.admin_handlers._resolve_category_with_range", side_effect=mock_resolve):
                    app = _make_admin_app()
                    client: TestClient = await aiohttp_client(app)
                    
                    resp = await client.post(
                        "/api/admin/conversions",
                        json={"range": "1d", "categories": [1, 2]},
                        headers={"X-Telegram-Init-Data": admin_init_data},
                    )
        
        assert resp.status == 200
        body = await resp.json()
        
        assert len(body["conversions"]) == 1
        conv = body["conversions"][0]
        assert conv["numerator"] == 0
        assert conv["denominator"] == 0
        assert conv["percent"] is None  # Division by zero → null

    @pytest.mark.asyncio
    async def test_conversions_invalid_category_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Invalid category numbers should return 400."""
        mock_categories = {1: ("Valid", []), 2: ("Valid", [])}
        
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch("api.admin_handlers.CONVERSION_CATEGORIES", mock_categories):
                app = _make_admin_app()
                client: TestClient = await aiohttp_client(app)
                
                resp = await client.post(
                    "/api/admin/conversions",
                    json={"range": "1d", "categories": [1, 999]},
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )
        
        assert resp.status == 400
        body = await resp.json()
        assert "error" in body
        assert "999" in body["error"]

    @pytest.mark.asyncio
    async def test_conversions_empty_categories_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Empty categories list should return 400."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            
            resp = await client.post(
                "/api/admin/conversions",
                json={"range": "1d", "categories": []},
                headers={"X-Telegram-Init-Data": admin_init_data},
            )
        
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_conversions_percent_rounding(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Percent should be rounded to 1 decimal place."""
        mock_categories = {
            1: ("Group A", []),
            2: ("Group B", []),
        }
        
        call_count = 0
        async def mock_resolve(source: Any, range_start: Any, range_end: Any) -> tuple[list[int], bool]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Category 1: 7 users
                return [1, 2, 3, 4, 5, 6, 7], True
            else:  # Category 2: 2 users (overlap)
                return [1, 2], True
        
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch("api.admin_handlers.CONVERSION_CATEGORIES", mock_categories):
                with patch("api.admin_handlers._resolve_category_with_range", side_effect=mock_resolve):
                    app = _make_admin_app()
                    client: TestClient = await aiohttp_client(app)
                    
                    resp = await client.post(
                        "/api/admin/conversions",
                        json={"range": "1d", "categories": [1, 2]},
                        headers={"X-Telegram-Init-Data": admin_init_data},
                    )
        
        assert resp.status == 200
        body = await resp.json()
        
        conv = body["conversions"][0]
        # 2/7 * 100 = 28.571... → should round to 28.6
        assert conv["percent"] == 28.6


# ---------------------------------------------------------------------------
# Broadcast handler: auth, validation, response
# ---------------------------------------------------------------------------


class TestBroadcastHandler:
    """Test POST /api/admin/broadcast: auth, validation, and response shape."""

    @pytest.mark.asyncio
    async def test_broadcast_missing_init_data_returns_401(
        self, aiohttp_client: Any
    ) -> None:
        """Missing X-Telegram-Init-Data header should return 401."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_broadcast=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.post(
                "/api/admin/broadcast",
                json={"category": 1, "message": "Hello"},
            )

        assert resp.status == 401
        body = await resp.json()
        assert "error" in body

    @pytest.mark.asyncio
    async def test_broadcast_non_admin_returns_403(
        self, aiohttp_client: Any, non_admin_init_data: str
    ) -> None:
        """Valid initData for non-admin user should return 403."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_broadcast=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.post(
                "/api/admin/broadcast",
                json={"category": 1, "message": "Hello"},
                headers={"X-Telegram-Init-Data": non_admin_init_data},
            )

        assert resp.status == 403
        body = await resp.json()
        assert "error" in body
        assert "forbidden" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_broadcast_invalid_category_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Invalid category number should return 400."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_broadcast=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.post(
                "/api/admin/broadcast",
                json={"category": 999, "message": "Hello"},
                headers={"X-Telegram-Init-Data": admin_init_data},
            )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body
        assert "999" in body["error"]

    @pytest.mark.asyncio
    async def test_broadcast_empty_message_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Empty message should return 400."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_broadcast=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.post(
                "/api/admin/broadcast",
                json={"category": 1, "message": ""},
                headers={"X-Telegram-Init-Data": admin_init_data},
            )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body

    @pytest.mark.asyncio
    async def test_broadcast_success_returns_sent_failed_total(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Successful broadcast should return sent, failed, total."""
        async def mock_resolve(_source: Any) -> list[int]:
            return [100, 200, 300]

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=None)

        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch("api.admin_handlers._resolve_user_ids", side_effect=mock_resolve):
                app = _make_admin_app(include_broadcast=True)
                app["bot"] = mock_bot
                client: TestClient = await aiohttp_client(app)

                resp = await client.post(
                    "/api/admin/broadcast",
                    json={"category": 1, "message": "Test message"},
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 200
        body = await resp.json()
        assert body["sent"] == 3
        assert body["failed"] == 0
        assert body["total"] == 3


# ---------------------------------------------------------------------------
# Task 5.1: GET /api/admin/prices auth and response tests
# ---------------------------------------------------------------------------


class TestPricesListHandler:
    """Test GET /api/admin/prices: auth required, returns rows."""

    @pytest.mark.asyncio
    async def test_prices_list_missing_init_data_returns_401(
        self, aiohttp_client: Any
    ) -> None:
        """Missing X-Telegram-Init-Data header should return 401."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_prices=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.get("/api/admin/prices")

        assert resp.status == 401
        body = await resp.json()
        assert "error" in body
        assert "initdata" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_prices_list_non_admin_returns_403(
        self, aiohttp_client: Any, non_admin_init_data: str
    ) -> None:
        """Valid initData for non-admin user should return 403."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_prices=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.get(
                "/api/admin/prices",
                headers={"X-Telegram-Init-Data": non_admin_init_data},
            )

        assert resp.status == 403
        body = await resp.json()
        assert "error" in body
        assert "forbidden" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_prices_list_returns_all_prices(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """GET /api/admin/prices should return all price rows."""
        mock_prices = [
            Price(
                option=ProductOption.SINGLE,
                price=100,
                reports_amount=1,
            ),
            Price(
                option=ProductOption.PACKET,
                price=500,
                reports_amount=10,
            ),
            Price(
                option=ProductOption.PACKET_FIRST,
                price=1000,
                reports_amount=5,
            ),
        ]

        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch(
                "api.admin_handlers.get_all_prices", return_value=mock_prices
            ):
                app = _make_admin_app(include_prices=True)
                client: TestClient = await aiohttp_client(app)

                resp = await client.get(
                    "/api/admin/prices",
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 200
        body = await resp.json()
        assert "prices" in body
        assert len(body["prices"]) == 3

        # Verify structure of returned rows
        assert body["prices"][0]["option"] == "SINGLE"
        assert body["prices"][0]["price"] == 100
        assert body["prices"][0]["reports_amount"] == 1

        assert body["prices"][1]["option"] == "PACKET"
        assert body["prices"][1]["price"] == 500
        assert body["prices"][1]["reports_amount"] == 10

        assert body["prices"][2]["option"] == "PACKET_FIRST"
        assert body["prices"][2]["price"] == 1000
        assert body["prices"][2]["reports_amount"] == 5

    @pytest.mark.asyncio
    async def test_prices_list_returns_empty_list_when_no_prices(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """GET /api/admin/prices should return empty list when no prices exist."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch("api.admin_handlers.get_all_prices", return_value=[]):
                app = _make_admin_app(include_prices=True)
                client: TestClient = await aiohttp_client(app)

                resp = await client.get(
                    "/api/admin/prices",
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 200
        body = await resp.json()
        assert "prices" in body
        assert body["prices"] == []


# ---------------------------------------------------------------------------
# Task 5.2: POST /api/admin/prices bulk update happy path
# ---------------------------------------------------------------------------


class TestPricesUpdateHandler:
    """Test POST /api/admin/prices: bulk update happy path."""

    @pytest.mark.asyncio
    async def test_prices_update_success(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """POST /api/admin/prices should successfully update prices."""
        request_data = {
            "prices": [
                {"option": "SINGLE", "price": 150, "reports_amount": 1},
                {"option": "PACKET", "price": 600, "reports_amount": 10},
            ]
        }

        mock_updated_prices = [
            Price(option=ProductOption.SINGLE, price=150, reports_amount=1),
            Price(option=ProductOption.PACKET, price=600, reports_amount=10),
        ]

        mock_bulk_upsert = AsyncMock(return_value=mock_updated_prices)

        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch(
                "api.admin_handlers.bulk_upsert_prices", mock_bulk_upsert
            ):
                app = _make_admin_app(include_prices=True)
                client: TestClient = await aiohttp_client(app)

                resp = await client.post(
                    "/api/admin/prices",
                    json=request_data,
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 200
        body = await resp.json()

        # Verify response structure
        assert "updated" in body
        assert "prices" in body
        assert body["updated"] == 2
        assert len(body["prices"]) == 2

        # Verify returned prices
        assert body["prices"][0]["option"] == "SINGLE"
        assert body["prices"][0]["price"] == 150
        assert body["prices"][0]["reports_amount"] == 1

        assert body["prices"][1]["option"] == "PACKET"
        assert body["prices"][1]["price"] == 600
        assert body["prices"][1]["reports_amount"] == 10

        # Verify bulk_upsert_prices was called with correct data
        assert mock_bulk_upsert.called
        call_args = mock_bulk_upsert.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0].option == ProductOption.SINGLE
        assert call_args[0].price == 150
        assert call_args[1].option == ProductOption.PACKET
        assert call_args[1].price == 600

    @pytest.mark.asyncio
    async def test_prices_update_single_price(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """POST /api/admin/prices should work with a single price."""
        request_data = {
            "prices": [{"option": "PACKET_SECOND", "price": 1200, "reports_amount": 15}]
        }

        mock_updated_prices = [
            Price(option=ProductOption.PACKET_SECOND, price=1200, reports_amount=15)
        ]

        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch(
                "api.admin_handlers.bulk_upsert_prices",
                return_value=mock_updated_prices,
            ):
                app = _make_admin_app(include_prices=True)
                client: TestClient = await aiohttp_client(app)

                resp = await client.post(
                    "/api/admin/prices",
                    json=request_data,
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 200
        body = await resp.json()
        assert body["updated"] == 1
        assert len(body["prices"]) == 1
        assert body["prices"][0]["option"] == "PACKET_SECOND"


# ---------------------------------------------------------------------------
# Task 5.3: POST /api/admin/prices validation failures
# ---------------------------------------------------------------------------


class TestPricesUpdateValidation:
    """Test POST /api/admin/prices: validation failures and no partial updates."""

    @pytest.mark.asyncio
    async def test_prices_update_missing_init_data_returns_401(
        self, aiohttp_client: Any
    ) -> None:
        """Missing X-Telegram-Init-Data header should return 401."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_prices=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.post(
                "/api/admin/prices",
                json={"prices": [{"option": "SINGLE", "price": 100, "reports_amount": 1}]},
            )

        assert resp.status == 401
        body = await resp.json()
        assert "error" in body

    @pytest.mark.asyncio
    async def test_prices_update_non_admin_returns_403(
        self, aiohttp_client: Any, non_admin_init_data: str
    ) -> None:
        """Valid initData for non-admin user should return 403."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_prices=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.post(
                "/api/admin/prices",
                json={"prices": [{"option": "SINGLE", "price": 100, "reports_amount": 1}]},
                headers={"X-Telegram-Init-Data": non_admin_init_data},
            )

        assert resp.status == 403
        body = await resp.json()
        assert "error" in body
        assert "forbidden" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_prices_update_invalid_json_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Malformed JSON should return 400."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_prices=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.post(
                "/api/admin/prices",
                data="not-json",
                headers={
                    "X-Telegram-Init-Data": admin_init_data,
                    "Content-Type": "application/json",
                },
            )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body
        assert "json" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_prices_update_empty_prices_list_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Empty prices list should return 400."""
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app(include_prices=True)
            client: TestClient = await aiohttp_client(app)

            resp = await client.post(
                "/api/admin/prices",
                json={"prices": []},
                headers={"X-Telegram-Init-Data": admin_init_data},
            )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body

    @pytest.mark.asyncio
    async def test_prices_update_invalid_option_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Invalid product option should return 400."""
        mock_bulk_upsert = AsyncMock()

        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch(
                "api.admin_handlers.bulk_upsert_prices", mock_bulk_upsert
            ):
                app = _make_admin_app(include_prices=True)
                client: TestClient = await aiohttp_client(app)

                resp = await client.post(
                    "/api/admin/prices",
                    json={
                        "prices": [
                            {"option": "INVALID_OPTION", "price": 100, "reports_amount": 1}
                        ]
                    },
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body
        assert "invalid product option" in body["error"].lower()

        # Verify bulk_upsert_prices was NOT called
        assert not mock_bulk_upsert.called

    @pytest.mark.asyncio
    async def test_prices_update_negative_price_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Negative price should return 400 and not call bulk_upsert_prices."""
        mock_bulk_upsert = AsyncMock()

        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch(
                "api.admin_handlers.bulk_upsert_prices", mock_bulk_upsert
            ):
                app = _make_admin_app(include_prices=True)
                client: TestClient = await aiohttp_client(app)

                resp = await client.post(
                    "/api/admin/prices",
                    json={
                        "prices": [
                            {"option": "SINGLE", "price": -100, "reports_amount": 1}
                        ]
                    },
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body
        assert "invalid request" in body["error"].lower()
        assert "greater than or equal to 0" in body["error"].lower()

        # Verify bulk_upsert_prices was NOT called (Pydantic validation fails first)
        assert not mock_bulk_upsert.called

    @pytest.mark.asyncio
    async def test_prices_update_zero_reports_amount_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Zero reports_amount should return 400 and not perform partial update."""
        mock_bulk_upsert = AsyncMock()

        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch(
                "api.admin_handlers.bulk_upsert_prices", mock_bulk_upsert
            ):
                app = _make_admin_app(include_prices=True)
                client: TestClient = await aiohttp_client(app)

                resp = await client.post(
                    "/api/admin/prices",
                    json={
                        "prices": [
                            {"option": "SINGLE", "price": 100, "reports_amount": 0},
                            {"option": "PACKET", "price": 500, "reports_amount": 10},
                        ]
                    },
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body
        assert "invalid request" in body["error"].lower()
        assert "greater than 0" in body["error"].lower()

        # Verify bulk_upsert_prices was NOT called (Pydantic validation fails first)
        assert not mock_bulk_upsert.called

    @pytest.mark.asyncio
    async def test_prices_update_mixed_valid_invalid_returns_400_no_partial_update(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Mixed valid/invalid prices should return 400 with no partial update."""
        mock_bulk_upsert = AsyncMock()

        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch(
                "api.admin_handlers.bulk_upsert_prices", mock_bulk_upsert
            ):
                app = _make_admin_app(include_prices=True)
                client: TestClient = await aiohttp_client(app)

                resp = await client.post(
                    "/api/admin/prices",
                    json={
                        "prices": [
                            {"option": "SINGLE", "price": 100, "reports_amount": 1},
                            {"option": "PACKET", "price": 500, "reports_amount": -5},
                        ]
                    },
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body
        assert "invalid request" in body["error"].lower()

        # Verify bulk_upsert_prices was NOT called
        # Pydantic validates ALL rows before any DB operations
        assert not mock_bulk_upsert.called

    @pytest.mark.asyncio
    async def test_prices_update_missing_required_fields_returns_400(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        """Missing required fields should return 400."""
        mock_bulk_upsert = AsyncMock()

        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            with patch(
                "api.admin_handlers.bulk_upsert_prices", mock_bulk_upsert
            ):
                app = _make_admin_app(include_prices=True)
                client: TestClient = await aiohttp_client(app)

                resp = await client.post(
                    "/api/admin/prices",
                    json={"prices": [{"option": "SINGLE", "price": 100}]},
                    headers={"X-Telegram-Init-Data": admin_init_data},
                )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body

        # Verify bulk_upsert_prices was NOT called (Pydantic validation fails first)
        assert not mock_bulk_upsert.called
