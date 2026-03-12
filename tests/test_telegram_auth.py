"""Tests for Telegram WebApp initData verification and admin auth middleware."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient

from api.telegram_auth import (
    TelegramWebAppUser,
    extract_user,
    parse_init_data,
    verify_init_data,
)

BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"  # nosec B105


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_init_data(
    params: dict[str, str],
    bot_token: str = BOT_TOKEN,
    *,
    tamper_hash: str | None = None,
) -> str:
    """Build a properly signed initData string.

    If *tamper_hash* is provided it replaces the computed hash (useful for
    testing invalid signatures).
    """
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


# ---------------------------------------------------------------------------
# parse_init_data
# ---------------------------------------------------------------------------


class TestParseInitData:
    def test_basic_parsing(self) -> None:
        raw = "auth_date=1234567890&query_id=AAHdF&user=%7B%22id%22%3A12345%7D&hash=abc"
        result = parse_init_data(raw)
        assert result["auth_date"] == "1234567890"
        assert result["query_id"] == "AAHdF"
        assert result["hash"] == "abc"
        assert json.loads(result["user"]) == {"id": 12345}

    def test_empty_string(self) -> None:
        assert parse_init_data("") == {}


# ---------------------------------------------------------------------------
# verify_init_data
# ---------------------------------------------------------------------------


class TestVerifyInitData:
    def test_valid_signature(self) -> None:
        params = {
            "auth_date": "1700000000",
            "query_id": "AAHdF",
            "user": _make_user_json(),
        }
        raw = _build_init_data(params)
        assert verify_init_data(raw, BOT_TOKEN) is True

    def test_invalid_signature(self) -> None:
        params = {
            "auth_date": "1700000000",
            "query_id": "AAHdF",
            "user": _make_user_json(),
        }
        raw = _build_init_data(params, tamper_hash="0" * 64)
        assert verify_init_data(raw, BOT_TOKEN) is False

    def test_missing_hash(self) -> None:
        raw = urlencode({"auth_date": "1700000000", "user": _make_user_json()})
        assert verify_init_data(raw, BOT_TOKEN) is False

    def test_wrong_bot_token(self) -> None:
        params = {"auth_date": "1700000000", "user": _make_user_json()}
        raw = _build_init_data(params, bot_token=BOT_TOKEN)
        assert verify_init_data(raw, "9999999999:WRONGtoken") is False

    def test_extra_fields_preserved(self) -> None:
        params = {
            "auth_date": "1700000000",
            "user": _make_user_json(),
            "chat_instance": "abc",
        }
        raw = _build_init_data(params)
        assert verify_init_data(raw, BOT_TOKEN) is True


# ---------------------------------------------------------------------------
# extract_user
# ---------------------------------------------------------------------------


class TestExtractUser:
    def test_extracts_user(self) -> None:
        user_json = _make_user_json(user_id=42, username="alice", last_name="Smith")
        params = {"auth_date": "1700000000", "user": user_json}
        raw = _build_init_data(params)

        user = extract_user(raw)
        assert user is not None
        assert user.id == 42
        assert user.first_name == "Test"
        assert user.last_name == "Smith"
        assert user.username == "alice"

    def test_missing_user_field(self) -> None:
        params = {"auth_date": "1700000000"}
        raw = _build_init_data(params)
        assert extract_user(raw) is None

    def test_malformed_user_json(self) -> None:
        params = {"auth_date": "1700000000", "user": "not-json"}
        raw = _build_init_data(params)
        assert extract_user(raw) is None


# ---------------------------------------------------------------------------
# admin_auth_middleware (integration via aiohttp TestClient)
# ---------------------------------------------------------------------------

_MOCK_SETTINGS = type(
    "MockSettings",
    (),
    {"bot_token": BOT_TOKEN, "admin_id_list": [111]},
)()


def _make_admin_app() -> web.Application:
    """Create a minimal app with the admin auth middleware for testing."""
    from api.admin_auth import admin_auth_middleware

    async def admin_handler(request: web.Request) -> web.Response:
        user: TelegramWebAppUser = request["tg_user"]
        return web.json_response({"ok": True, "user_id": user.id})

    async def public_handler(_request: web.Request) -> web.Response:
        return web.json_response({"public": True})

    app = web.Application(middlewares=[admin_auth_middleware])  # type: ignore[list-item]
    app.router.add_get("/api/admin/test", admin_handler)
    app.router.add_get("/health", public_handler)
    return app


@pytest.fixture
def admin_init_data() -> str:
    params = {"auth_date": "1700000000", "user": _make_user_json(user_id=111)}
    return _build_init_data(params)


@pytest.fixture
def non_admin_init_data() -> str:
    params = {"auth_date": "1700000000", "user": _make_user_json(user_id=999)}
    return _build_init_data(params)


class TestAdminAuthMiddleware:
    """Middleware integration tests — patch ``settings`` for the request duration."""

    @pytest.mark.asyncio
    async def test_missing_header_returns_401(self, aiohttp_client: Any) -> None:
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            resp = await client.get("/api/admin/test")
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        tampered = admin_init_data[:-8] + "00000000"
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            resp = await client.get(
                "/api/admin/test",
                headers={"X-Telegram-Init-Data": tampered},
            )
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(
        self, aiohttp_client: Any, non_admin_init_data: str
    ) -> None:
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            resp = await client.get(
                "/api/admin/test",
                headers={"X-Telegram-Init-Data": non_admin_init_data},
            )
        assert resp.status == 403

    @pytest.mark.asyncio
    async def test_admin_allowed(
        self, aiohttp_client: Any, admin_init_data: str
    ) -> None:
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            resp = await client.get(
                "/api/admin/test",
                headers={"X-Telegram-Init-Data": admin_init_data},
            )
        assert resp.status == 200
        body = await resp.json()
        assert body == {"ok": True, "user_id": 111}

    @pytest.mark.asyncio
    async def test_non_admin_path_passes_through(self, aiohttp_client: Any) -> None:
        with patch("api.admin_auth.settings", _MOCK_SETTINGS):
            app = _make_admin_app()
            client: TestClient = await aiohttp_client(app)
            resp = await client.get("/health")
        assert resp.status == 200
        body = await resp.json()
        assert body == {"public": True}
