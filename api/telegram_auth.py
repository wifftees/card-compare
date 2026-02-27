"""Telegram WebApp initData verification.

Implements the server-side HMAC-SHA256 validation algorithm described at
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramWebAppUser:
    """Minimal representation of the ``user`` object inside initData."""

    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""


def _make_secret_key(bot_token: str) -> bytes:
    """Derive the HMAC secret from the bot token per Telegram algorithm."""
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def parse_init_data(raw: str) -> dict[str, str]:
    """Parse URL-encoded ``initData`` string into a flat dict.

    Each key maps to its *first* value (Telegram sends single-valued params).
    Values are URL-decoded.
    """
    parsed = parse_qs(raw, keep_blank_values=True)
    return {k: v[0] for k, v in parsed.items()}


def verify_init_data(raw: str, bot_token: str) -> bool:
    """Verify ``initData`` HMAC-SHA256 signature.

    Returns ``True`` when the signature is valid, ``False`` otherwise.
    Does **not** enforce ``auth_date`` freshness — callers may add that check.
    """
    params = parse_init_data(raw)
    received_hash = params.pop("hash", None)
    if not received_hash:
        return False

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    secret_key = _make_secret_key(bot_token)
    computed = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed, received_hash)


def extract_user(raw: str) -> TelegramWebAppUser | None:
    """Extract ``TelegramWebAppUser`` from *already-verified* initData.

    Returns ``None`` if the ``user`` field is missing or malformed.
    """
    params = parse_init_data(raw)
    user_json = params.get("user")
    if not user_json:
        return None
    try:
        data = json.loads(user_json)
        return TelegramWebAppUser(
            id=int(data["id"]),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            username=data.get("username", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning("Failed to parse user from initData")
        return None
