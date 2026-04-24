"""Wildberries Playwright client"""

import logging
from playwright.async_api import (
    Error as PlaywrightError,
    async_playwright,
    Browser,
    BrowserContext,
    Page,
)

from bot.utils.status import update_status_message
from database.queries import get_compare_cards_mock
from .auth_service import WBAuthService
from .scraper_service import WBScraperService, StatusCallback
from .config import WBConfig
from .state_storage import StateStorage

logger = logging.getLogger(__name__)


class WBClient:
    """Client for working with Wildberries Seller platform"""

    def __init__(
        self,
        config: WBConfig,
        state_storage: StateStorage,
        bot=None,
        admin_id: int = None,
    ):
        self._config = config
        self._state_storage = state_storage
        self._bot = bot
        self._admin_id = admin_id
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._auth_service: WBAuthService | None = None
        self._scraper_service: WBScraperService | None = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()

    def _bind_services(self, page: Page) -> None:
        """Bind services to the current Playwright page."""
        self._page = page
        self._page.on("close", lambda: logger.warning("⚠️  Page closed!"))
        self._auth_service = WBAuthService(
            self._page,
            self._context,
            self._config,
            self._state_storage,
            bot=self._bot,
            admin_id=self._admin_id,
        )
        self._scraper_service = WBScraperService(
            self._page, self._config.downloads_path
        )

    def _has_live_page(self) -> bool:
        """Return True when the current page can still be used."""
        return self._page is not None and not self._page.is_closed()

    def _has_live_browser(self) -> bool:
        """Return True when the current browser connection is still alive."""
        return self._browser is not None and self._browser.is_connected()

    async def _open_page(self) -> Page:
        """Open a fresh page inside the current browser context."""
        if not self._context:
            raise RuntimeError("Browser context not initialized")

        page = await self._context.new_page()
        self._bind_services(page)
        await self._verify_locale()
        return page

    async def ensure_page(self, *, force_recreate: bool = False) -> Page:
        """Restore the Playwright page if it was closed unexpectedly."""
        if not force_recreate and self._has_live_page():
            if not self._auth_service or not self._scraper_service:
                logger.warning("⚠️  Browser services missing, rebinding current page")
                self._bind_services(self._page)
            return self._page

        logger.warning("⚠️  Browser page is unavailable, restoring it...")

        if force_recreate and self._has_live_page():
            try:
                await self._page.close()
            except PlaywrightError as e:
                logger.warning(f"⚠️  Could not close stale page cleanly: {e}")

        if self._has_live_browser() and self._context is not None:
            try:
                page = await self._open_page()
                logger.info("✅ Browser page restored in existing context")
                return page
            except PlaywrightError as e:
                logger.warning(
                    f"⚠️  Could not restore page in current context: {e}"
                )

        logger.info("🔄 Reconnecting browser runtime from scratch...")
        await self.disconnect()
        await self.connect()
        if not self._page:
            raise RuntimeError("Failed to restore browser page")
        return self._page

    async def ensure_authorized(self) -> None:
        """Ensure the browser is alive and authenticated before scraping."""
        last_error: Exception | None = None

        for attempt in range(2):
            await self.ensure_page(force_recreate=attempt > 0)
            if not self._auth_service:
                raise RuntimeError("Auth service is not initialized")

            try:
                await self._auth_service.ensure_authorized()
                return
            except PlaywrightError as e:
                error_text = str(e).lower()
                if "target page" not in error_text and "has been closed" not in error_text:
                    raise

                last_error = e
                logger.warning(
                    "⚠️  Browser page closed during authorization, retrying..."
                )

        raise RuntimeError("Failed to restore browser page for authorization") from last_error

    async def connect(self):
        """Initialize browser and connect"""
        logger.info("🚀 Starting browser...")
        self._playwright = await async_playwright().start()

        # Additional arguments for stable Docker operation
        launch_args = []
        if self._config.headless:
            launch_args.extend(
                [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )

        self._browser = await self._playwright.firefox.launch(
            headless=self._config.headless,
            slow_mo=self._config.slow_mo,
            args=launch_args,
        )

        # Add browser disconnection handler for debugging
        self._browser.on(
            "disconnected", lambda: logger.warning("⚠️  Browser disconnected!")
        )

        context_options = {"locale": "ru-RU", "timezone_id": "Europe/Moscow"}

        # Load saved state if exists
        logger.info("📂 Attempting to load saved state...")
        state = await self._state_storage.load_state()
        if state:
            logger.info("✅ Valid state found, loading into browser context...")
            self._context = await self._browser.new_context(
                storage_state=state, **context_options
            )
            logger.info("✅ Browser context created with saved state")
        else:
            logger.warning(
                "⚠️  No valid state available - fresh authentication will be required"
            )
            self._context = await self._browser.new_context(**context_options)

        await self._open_page()

        # IMPORTANT: Do NOT call ensure_authorized() here!
        # It must be called AFTER bot polling starts to avoid deadlock.
        # Authorization is handled by Application.ensure_wb_authorized() background task.
        # See main.py start() method for details.

        logger.info(f"✅ Ready to work on page: {self._page.url}")

    async def disconnect(self):
        """Close browser"""
        try:
            if self._browser and self._browser.is_connected():
                await self._browser.close()
        except PlaywrightError as e:
            logger.warning(f"⚠️  Error while closing browser: {e}")
        finally:
            self._browser = None
            self._context = None
            self._page = None
            self._auth_service = None
            self._scraper_service = None

        try:
            if self._playwright:
                await self._playwright.stop()
        except PlaywrightError as e:
            logger.warning(f"⚠️  Error while stopping Playwright: {e}")
        finally:
            self._playwright = None

        logger.info("⏸️  Browser closed")

    async def _verify_locale(self):
        """Verify browser locale"""
        try:
            # Check language via JavaScript
            locale = await self._page.evaluate("() => navigator.language")
            languages = await self._page.evaluate("() => navigator.languages")
            timezone = await self._page.evaluate(
                "() => Intl.DateTimeFormat().resolvedOptions().timeZone"
            )

            logger.info(f"🌍 Browser locale: {locale}")
            logger.info(f"🌍 Browser languages: {languages}")
            logger.info(f"🕐 Timezone: {timezone}")

            # Check that locale is Russian
            if not locale.startswith("ru"):
                logger.warning(f"⚠️  Expected Russian locale, but got: {locale}")
            else:
                logger.info("✅ Russian locale confirmed")

        except Exception as e:
            logger.error(f"❌ Error verifying locale: {e}")

    def _create_status_callback(
        self,
        chat_id: int | None,
        status_message_id: int | None,
    ) -> StatusCallback | None:
        """Create a status update callback for scraper service."""
        bot = self._bot
        if not bot or not chat_id or not status_message_id:
            return None

        async def on_status(stage: int) -> bool:
            return await update_status_message(bot, chat_id, status_message_id, stage)

        return on_status

    async def compare_cards(
        self,
        articles: list[int],
        chat_id: int | None = None,
        status_message_id: int | None = None,
    ):
        """Compare cards by article numbers"""
        on_status = self._create_status_callback(chat_id, status_message_id)
        use_mock = await get_compare_cards_mock()
        if use_mock:
            logger.info("🎭 COMPARE_CARDS_MOCK is enabled, using fake_compare_cards")
            return await self._scraper_service.fake_compare_cards(
                articles, on_status=on_status
            )
        await self.ensure_authorized()
        if not self._scraper_service:
            raise RuntimeError("Scraper service is not initialized")
        return await self._scraper_service.compare_cards(articles, on_status=on_status)

    async def process_filters(
        self,
        chat_id: int | None = None,
        status_message_id: int | None = None,
    ) -> tuple[int, int]:
        """Process filters and create reports"""
        on_status = self._create_status_callback(chat_id, status_message_id)
        return await self._scraper_service.process_filters(on_status=on_status)

    async def download_documents(
        self,
        unique_id: int,
        expected_count: int,
        chat_id: int | None = None,
        status_message_id: int | None = None,
    ) -> str:
        """Download created documents and return path to merged ZIP"""
        on_status = self._create_status_callback(chat_id, status_message_id)
        return await self._scraper_service.download_documents(
            unique_id, expected_count, on_status=on_status
        )

    async def save_current_state(self):
        """Save current browser state to file"""
        if not self._context:
            logger.warning("⚠️  Cannot save state - browser context not initialized")
            return

        try:
            logger.info("💾 Saving current browser state...")
            state = await self._context.storage_state()
            await self._state_storage.save_state(state)
            logger.info("✅ Browser state saved successfully")
        except Exception as e:
            logger.error(f"❌ Error saving browser state: {e}")
