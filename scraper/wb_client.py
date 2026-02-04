"""Wildberries Playwright client"""
import asyncio
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from bot.config import settings
from database.queries import get_compare_cards_mock
from .auth_service import WBAuthService
from .scraper_service import WBScraperService
from .config import WBConfig
from .state_storage import StateStorage

logger = logging.getLogger(__name__)


class WBClient:
    """Client for working with Wildberries Seller platform"""
    
    def __init__(self, config: WBConfig, state_storage: StateStorage, bot=None, admin_id: int = None):
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
    
    async def connect(self):
        """Initialize browser and connect"""
        logger.info('🚀 Starting browser...')
        self._playwright = await async_playwright().start()
        
        # Additional arguments for stable Docker operation
        launch_args = []
        if self._config.headless:
            launch_args.extend([
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
            ])
        
        self._browser = await self._playwright.firefox.launch(
            headless=self._config.headless,
            slow_mo=self._config.slow_mo,
            args=launch_args
        )
        
        # Add browser disconnection handler for debugging
        self._browser.on('disconnected', lambda: logger.warning('⚠️  Browser disconnected!'))
        
        context_options = {
            'locale': 'ru-RU',
            'timezone_id': 'Europe/Moscow'
        }
        
        # Load saved state if exists
        logger.info('📂 Attempting to load saved state...')
        state = await self._state_storage.load_state()
        if state:
            logger.info('✅ Valid state found, loading into browser context...')
            self._context = await self._browser.new_context(storage_state=state, **context_options)
            logger.info('✅ Browser context created with saved state')
        else:
            logger.warning('⚠️  No valid state available - fresh authentication will be required')
            self._context = await self._browser.new_context(**context_options)
        
        self._page = await self._context.new_page()
        
        # Add page close handler for debugging
        self._page.on('close', lambda: logger.warning('⚠️  Page closed!'))
        
        # Verify browser locale
        await self._verify_locale()
        
        # Initialize services
        self._auth_service = WBAuthService(
            self._page, 
            self._context, 
            self._config, 
            self._state_storage,
            bot=self._bot,
            admin_id=self._admin_id
        )
        self._scraper_service = WBScraperService(self._page, self._config.downloads_path)
        
        # IMPORTANT: Do NOT call ensure_authorized() here!
        # It must be called AFTER bot polling starts to avoid deadlock.
        # Authorization is handled by Application.ensure_wb_authorized() background task.
        # See main.py start() method for details.
        
        logger.info(f'✅ Ready to work on page: {self._page.url}')
    
    async def disconnect(self):
        """Close browser"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info('⏸️  Browser closed')
    
    async def _verify_locale(self):
        """Verify browser locale"""
        try:
            # Check language via JavaScript
            locale = await self._page.evaluate('() => navigator.language')
            languages = await self._page.evaluate('() => navigator.languages')
            timezone = await self._page.evaluate('() => Intl.DateTimeFormat().resolvedOptions().timeZone')
            
            logger.info(f'🌍 Browser locale: {locale}')
            logger.info(f'🌍 Browser languages: {languages}')
            logger.info(f'🕐 Timezone: {timezone}')
            
            # Check that locale is Russian
            if not locale.startswith('ru'):
                logger.warning(f'⚠️  Expected Russian locale, but got: {locale}')
            else:
                logger.info('✅ Russian locale confirmed')
                
        except Exception as e:
            logger.error(f'❌ Error verifying locale: {e}')
    
    async def compare_cards(self, articles: list[int]):
        """Compare cards by article numbers"""
        use_mock = await get_compare_cards_mock()
        if use_mock:
            logger.info('🎭 COMPARE_CARDS_MOCK is enabled, using fake_compare_cards')
            return await self._scraper_service.fake_compare_cards(articles)
        return await self._scraper_service.compare_cards(articles)
    
    async def process_filters(self) -> tuple[int, int]:
        """Process filters and create reports"""
        return await self._scraper_service.process_filters()
    
    async def download_documents(self, unique_id: int, expected_count: int) -> str:
        """Download created documents and return path to merged ZIP"""
        return await self._scraper_service.download_documents(unique_id, expected_count)
    
    async def save_current_state(self):
        """Save current browser state to file"""
        if not self._context:
            logger.warning('⚠️  Cannot save state - browser context not initialized')
            return
        
        try:
            logger.info('💾 Saving current browser state...')
            state = await self._context.storage_state()
            await self._state_storage.save_state(state)
            logger.info('✅ Browser state saved successfully')
        except Exception as e:
            logger.error(f'❌ Error saving browser state: {e}')
