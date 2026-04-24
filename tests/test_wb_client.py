"""Tests for WBClient browser recovery."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from playwright.async_api import Error as PlaywrightError

from scraper.config import WBConfig
from scraper.wb_client import WBClient


@pytest.mark.asyncio
async def test_ensure_page_recreates_closed_page():
    """WBClient should recreate a closed page inside the existing context."""
    client = WBClient(config=WBConfig(phone="+79990000000"), state_storage=Mock())
    closed_page = Mock()
    closed_page.is_closed.return_value = True
    new_page = Mock()
    new_page.is_closed.return_value = False
    new_page.on = Mock()
    new_page.url = "about:blank"

    client._page = closed_page
    client._browser = Mock()
    client._browser.is_connected.return_value = True
    client._context = Mock()
    client._context.new_page = AsyncMock(return_value=new_page)
    client._verify_locale = AsyncMock()

    page = await client.ensure_page()

    assert page is new_page
    assert client._page is new_page
    assert client._auth_service is not None
    assert client._scraper_service is not None
    client._context.new_page.assert_awaited_once()
    client._verify_locale.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_authorized_retries_after_closed_page_error():
    """WBClient should reopen the page once if auth hits a closed-page error."""
    client = WBClient(config=WBConfig(phone="+79990000000"), state_storage=Mock())
    page = Mock()
    page.is_closed.return_value = False

    client.ensure_page = AsyncMock(return_value=page)
    client._auth_service = Mock()
    client._auth_service.ensure_authorized = AsyncMock(
        side_effect=[
            PlaywrightError("Target page, context or browser has been closed"),
            None,
        ]
    )

    await client.ensure_authorized()

    assert client.ensure_page.await_args_list[0].kwargs == {"force_recreate": False}
    assert client.ensure_page.await_args_list[1].kwargs == {"force_recreate": True}
    assert client._auth_service.ensure_authorized.await_count == 2
