"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Mock external dependencies before any test imports
sys.modules["aiogram"] = MagicMock()
sys.modules["aiogram.types"] = MagicMock()
sys.modules["supabase"] = MagicMock()
sys.modules["bot.handlers.admin"] = MagicMock()
sys.modules["bot.config"] = MagicMock()
sys.modules["database.client"] = MagicMock()

# Create a mock CONVERSION_CATEGORIES that tests can override
from database.models import EventType  # noqa: E402

MOCK_CONVERSION_CATEGORIES = {
    1: ("Started bot", [EventType.CLICK_START]),
    2: ("Clicked compare", [EventType.CLICK_COMPARE]),
    3: ("Generated report", []),
}

sys.modules["bot.handlers.admin"].CONVERSION_CATEGORIES = MOCK_CONVERSION_CATEGORIES  # type: ignore[attr-defined]
