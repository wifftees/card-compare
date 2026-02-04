"""Authentication service for Wildberries"""
import asyncio
import logging
from datetime import datetime
from playwright.async_api import Page, BrowserContext, TimeoutError as PlaywrightTimeoutError

from .state_storage import StateStorage

logger = logging.getLogger(__name__)


class WBAuthService:
    """Service for Wildberries authentication"""
    
    def __init__(self, page: Page, context: BrowserContext, config, state_storage: StateStorage, bot=None, admin_id: int = None):
        self._page = page
        self._context = context
        self._config = config
        self._state_storage = state_storage
        self._bot = bot
        self._admin_id = admin_id
        self._pending_code_future: asyncio.Future | None = None
    
    async def check_needs_authorization(self) -> bool:
        """Check if authorization is needed"""
        # Method 1: Check for phone input field (auth page)
        try:
            phone_input = self._page.get_by_test_id('phone-input')
            await phone_input.wait_for(state='visible', timeout=3000)
            logger.info('🔍 Found phone input field - authorization needed')
            return True
        except PlaywrightTimeoutError:
            pass
        
        # Method 2: Check URL for auth redirect
        current_url = self._page.url
        if 'seller-auth' in current_url or 'auth' in current_url:
            logger.info(f'🔍 URL contains auth - authorization needed: {current_url}')
            return True
        
        # Method 3: Check if we're on the target page
        if 'cards-comparison' in current_url:
            logger.info(f'🔍 Already on target page - authorization not needed: {current_url}')
            return False
        
        logger.info(f'🔍 Unclear state, URL: {current_url}')
        return False
    
    async def authorize(self):
        """Semi-automatic authorization function"""
        logger.info('🔐 Starting authorization process...')
        
        logger.info('🔍 Waiting for phone input field...')
        phone_input = self._page.get_by_test_id('phone-input')
        await phone_input.wait_for(state='visible', timeout=15000)
        logger.info('✅ Phone input field found')
        
        logger.info(f'⌨️  Entering phone number: {self._config.phone}')
        await phone_input.fill(self._config.phone)
        logger.info('✅ Phone number entered')
        
        logger.info('🖱️  Clicking submit button...')
        submit_button = self._page.get_by_test_id('submit-phone-button')
        await submit_button.click()
        logger.info('✅ Submit button clicked')
        
        # Wait for page to process
        await self._page.wait_for_timeout(2000)
        
        logger.info('🔍 Waiting for code input form...')
        logger.info(f'📄 Current URL: {self._page.url}')
        
        # Try multiple selectors for code form
        code_form = None
        selectors = [
            '.FormCodeInput ul',
            '[class*="FormCodeInput"] ul',
            'ul[class*="code"]',
            'input[type="tel"]',
            'input[inputmode="numeric"]'
        ]
        
        logger.info('✅ Code input form appeared')
        
        # Request code via Telegram if bot is configured
        if self._bot and self._admin_id:
            logger.info('📱 Requesting auth code via Telegram...')
            code = await self._request_code_via_telegram()
        else:
            # Fallback to console input (for development)
            logger.warning('⚠️ Bot not configured, using console input')
            loop = asyncio.get_event_loop()
            code = await loop.run_in_executor(None, input, '\n📱 Enter confirmation code: ')
        
        code = code.strip()  # Remove any whitespace
        logger.info(f'✅ Received code with length {len(code)}')
        
        if len(code) == 0:
            raise Exception('Empty code received')
        
        logger.info('⌨️  Entering code digits...')
        
        # Find code form container
        code_form = self._page.locator('.FormCodeInput ul')
        await code_form.wait_for(state='visible', timeout=10000)
        logger.info(f'✅ Code form container found')
        
        # Enter each digit of the code in corresponding input
        for i, digit in enumerate(code):
            try:
                # Find specific input by index in list item
                digit_input = code_form.locator(f'li:nth-child({i + 1}) input')
                await digit_input.wait_for(state='visible', timeout=5000)
                
                # If this is the last digit, wait for navigation after input
                if i == len(code) - 1:
                    logger.info(f'⌨️  Entering last digit ({i + 1}/{len(code)})...')
                    await digit_input.fill(digit)
                    # After entering last digit, wait for redirect
                    logger.info('⏳ Waiting for redirect...')
                    redirect_successful = False
                    try:
                        await self._page.wait_for_url('**/platform-analytics/cards-comparison', timeout=15000)
                        logger.info('✅ Redirect successful')
                        redirect_successful = True
                    except PlaywrightTimeoutError:
                        # If redirect didn't happen in 15 sec, check current URL
                        current_url = self._page.url
                        if 'cards-comparison' in current_url:
                            logger.info('✅ Redirect successful (already on page)')
                            redirect_successful = True
                        else:
                            logger.warning(f'⚠️  Redirect timeout. Current URL: {current_url}')
                            logger.info('🔍 This may indicate incorrect code or network issues')
                    except Exception as e:
                        logger.error(f'❌ Error waiting for navigation: {e}')
                        logger.info('🔍 Will verify authorization in final check')
                else:
                    logger.info(f'⌨️  Entering digit {i + 1}/{len(code)}...')
                    await digit_input.fill(digit)
                    # Small delay between entering digits
                    await self._page.wait_for_timeout(200)
            except Exception as e:
                logger.error(f'❌ Error entering digit {i + 1}: {e}')
                raise
        
        logger.info('⏳ Waiting for page to load...')
        # Additional check: wait for page to stabilize
        try:
            await self._page.wait_for_load_state('domcontentloaded', timeout=5000)
        except PlaywrightTimeoutError:
            pass  # Ignore if page is already loaded
        
        # CRITICAL: Verify we're on the correct page BEFORE saving state
        logger.info('🔍 Verifying successful authorization...')
        current_url = self._page.url
        
        if 'cards-comparison' not in current_url:
            # Check if we need to navigate again or if auth failed
            if 'auth' in current_url or 'seller-auth' in current_url:
                error_msg = f'❌ Authorization failed - still on auth page: {current_url}'
                logger.error(error_msg)
            else:
                logger.warning(f'⚠️  Not on cards-comparison page: {current_url}')
                logger.info('🔄 Attempting to navigate to cards-comparison...')
                try:
                    await self._page.goto(
                        'https://seller.wildberries.ru/platform-analytics/cards-comparison',
                        wait_until='domcontentloaded',
                        timeout=10000
                    )
                    current_url = self._page.url
                    if 'cards-comparison' not in current_url:
                        raise Exception(f'Failed to navigate to cards-comparison. URL: {current_url}')
                    logger.info('✅ Navigation successful')
                except Exception as e:
                    logger.error(f'❌ Navigation failed: {e}')
                    raise Exception(f'Authorization incomplete - cannot reach target page: {e}')
        
        logger.info(f'✅ Authorization verified - on correct page: {current_url}')
        
        # Save session state ONLY after verifying successful auth
        logger.info('💾 Saving session state...')
        state = await self._context.storage_state()
        await self._state_storage.save_state(state)
        logger.info('✅ Session state saved to file')
    
    async def ensure_authorized(self):
        """Check and perform authorization if needed"""
        logger.info('🌐 Navigating to page...')
        await self._page.goto(
            'https://seller.wildberries.ru/platform-analytics/cards-comparison',
            wait_until='domcontentloaded'
        )
        logger.info(f'✅ Page loaded: {self._page.url}')
        
        # Wait for page to fully load and stabilize
        logger.info('⏳ Waiting for page to stabilize...')
        try:
            await self._page.wait_for_load_state('networkidle', timeout=10000)
        except PlaywrightTimeoutError:
            logger.warning('⚠️  Network idle timeout, continuing anyway')
        
        # Wait a bit more for any redirects
        await self._page.wait_for_timeout(2000)
        logger.info(f'📍 Current URL after stabilization: {self._page.url}')
        
        # Check if authorization is needed
        logger.info('🔍 Checking if authorization is needed...')
        needs_auth = await self.check_needs_authorization()
        
        if needs_auth:
            logger.warning('⚠️  Authorization required!')
            logger.info('   This can happen due to:')
            logger.info('   1. Session expired on server side')
            logger.info('   2. Changed IP address or browser fingerprint')
            logger.info('   3. Cloudflare security check')
            logger.info('   4. Server security policy')
            logger.warning('🔄 Starting authorization process...')
            await self.authorize()
        else:
            logger.info('✅ Authorization not required, using saved session')
        
        # Check that we're on the correct page
        if 'cards-comparison' not in self._page.url:
            logger.warning(f'⚠️  Current URL does not match expected: {self._page.url}')
            logger.info('⏳ Navigating to cards-comparison page...')
            await self._page.goto(
                'https://seller.wildberries.ru/platform-analytics/cards-comparison',
                wait_until='domcontentloaded'
            )
    
    async def _request_code_via_telegram(self) -> str:
        """
        Request authentication code via Telegram bot.
        
        Creates a Future and sends notification to admin.
        Waits for admin to send the code via bot.
        
        Returns:
            str: The authentication code
            
        Raises:
            asyncio.TimeoutError: If no response within 5 minutes
            Exception: If failed to send notification
        """
        from datetime import datetime
        
        # Create Future for waiting
        self._pending_code_future = asyncio.Future()
        
        # Send notification to admin
        try:
            request_time = datetime.now().strftime('%H:%M:%S')
            await self._bot.send_message(
                chat_id=self._admin_id,
                text=(
                    "🔐 <b>Требуется код авторизации</b>\n\n"
                    f"📱 Номер: <code>{self._config.phone}</code>\n"
                    f"⏰ Время: {request_time}\n\n"
                    "Отправьте код сообщением (только цифры):"
                )
            )
            logger.info(f'✅ Notification sent to admin {self._admin_id}')
        except Exception as e:
            logger.error(f'❌ Failed to send notification: {e}')
            self._pending_code_future = None
            raise Exception(f'Cannot send auth code request to admin: {e}')
        
        # Wait for code with timeout (5 minutes)
        try:
            code = await asyncio.wait_for(self._pending_code_future, timeout=300)
            logger.info(f'✅ Code received via Telegram')
            return code
        except asyncio.TimeoutError:
            logger.error('❌ Timeout waiting for auth code (5 minutes)')
            raise Exception('Auth code timeout - no response from admin')
        finally:
            self._pending_code_future = None