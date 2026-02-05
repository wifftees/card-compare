"""Main application entry point"""
import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile

from bot.config import settings
from bot.queue import ReportQueue, ReportTask, ReportResult
from bot.middlewares.user_middleware import UserMiddleware
from bot.handlers import start, balance, reports, common

from database.client import SupabaseClient
from database.queries import update_balance, check_balance, get_wb_use_mock

# Browser test imports
from scraper.wb_client import WBClient
from scraper.config import WBConfig
from scraper.state_storage import StateStorage

from utils.logger import setup_logging

logger = logging.getLogger(__name__)


class Application:
    """Main application class"""
    
    def __init__(self):
        self.bot: Bot | None = None
        self.dp: Dispatcher | None = None
        self.wb_client: WBClient | None = None
        self.report_queue: ReportQueue | None = None
        self.worker_task: asyncio.Task | None = None
        self.result_processor_task: asyncio.Task | None = None
        self.auth_check_task: asyncio.Task | None = None
        self.state_saver_task: asyncio.Task | None = None
        self._shutdown = False
    
    async def process_report_real(self, articles: list[int]) -> str:
        """
        Real report processing using browser automation.
        
        Args:
            articles: List of article numbers to compare
            
        Returns:
            str: Path to the downloaded report file
        """
        logger.info(f"📦 Comparing {len(articles)} cards: {articles}")
        await self.wb_client.compare_cards(articles)
        logger.info("✅ Cards compared successfully")
        
        logger.info("📊 Generating filtered reports...")
        unique_id, count = await self.wb_client.process_filters()
        logger.info(f"✅ Filters processed: unique_id={unique_id}, count={count}")
        
        logger.info(f"📥 Downloading {count} documents...")
        file_path = await self.wb_client.download_documents(unique_id, count)
        logger.info(f"✅ Documents downloaded: {file_path}")
        
        return file_path
    
    async def process_report_mock(self, articles: list[int]) -> str:
        """
        Mock report processing returning a static test file.
        
        Args:
            articles: List of article numbers (logged but not used)
            
        Returns:
            str: Path to the static test report file
        """
        logger.info(f"📦 [MOCK] Comparing {len(articles)} cards: {articles}")
        logger.info("✅ [MOCK] Cards compared successfully (skipped)")
        
        logger.info("📊 [MOCK] Generating filtered reports (skipped)...")
        await asyncio.sleep(1)  # Simulate processing
        
        logger.info("📥 [MOCK] Downloading documents (skipped)...")
        await asyncio.sleep(1)  # Simulate download
        
        # Return static test file
        file_path = str(Path(__file__).parent / "storage" / "test_report.txt")
        logger.info(f"📄 [MOCK] Using static file: {file_path}")
        
        return file_path
    
    async def setup(self):
        """Setup application components"""
        logger.info("🚀 Starting application...")
        
        # Initialize Supabase
        logger.info("📊 Initializing Supabase client...")
        SupabaseClient.get_client()
        
        # Initialize bot FIRST (before WB client)
        logger.info("🤖 Initializing Telegram bot...")
        self.bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode="HTML")
        )
        storage = MemoryStorage()
        self.dp = Dispatcher(storage=storage)
        
        # Register middlewares
        logger.info("🔧 Registering middlewares...")
        self.dp.message.middleware(UserMiddleware())
        self.dp.callback_query.middleware(UserMiddleware())
        
        # Register handlers (including auth_code handler)
        logger.info("📝 Registering handlers...")
        
        # Import and register auth_code handler FIRST (before others)
        from bot.handlers import auth_code
        self.dp.include_router(auth_code.router)
        
        # Then register other handlers
        self.dp.include_router(start.router)
        self.dp.include_router(balance.router)
        self.dp.include_router(reports.router)
        
        # Register catch-all handler last
        self.dp.include_router(common.router)
        
        # Inject dependencies into handlers
        self.dp["app"] = self  # Make app accessible to handlers
        
        # Initialize Wildberries client WITH bot reference
        # logger.info("🌐 Initializing Wildberries client...")
        # wb_config = WBConfig(
        #     phone=settings.wb_phone,
        #     headless=settings.wb_headless,
        #     state_file_path=settings.wb_state_file,
        #     downloads_path=settings.wb_downloads_path
        # )
        # state_storage = StateStorage(settings.wb_state_file)
        # self.wb_client = WBClient(
        #     config=wb_config, 
        #     state_storage=state_storage,
        #     bot=self.bot,  # Pass bot instance
        #     admin_id=settings.admin_telegram_id  # Pass admin ID
        # )
        
        # Connect browser (may request auth code via Telegram)
        # logger.info("🔌 Connecting browser...")
        # await self.wb_client.connect()
        # logger.info("✅ Browser connected successfully!")
        
        # Initialize report queue
        logger.info("📥 Initializing report queue...")
        self.report_queue = ReportQueue(maxsize=0)  # Unlimited queue
        
        # Inject report_queue into handlers
        self.dp["report_queue"] = self.report_queue
        
        logger.info("✅ Application setup complete")
    
    async def queue_worker(self):
        """Worker that processes tasks from queue"""
        logger.info("🔄 Queue worker started")
        
        while not self._shutdown:
            try:
                # Get task from queue (with timeout to check shutdown flag)
                try:
                    task: ReportTask = await asyncio.wait_for(
                        self.report_queue.get_task(),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                logger.info(f"⚙️  Processing task {task.task_id}")
                
                try:
                    # Choose between real and mock processing
                    use_mock = await get_wb_use_mock()
                    if use_mock:
                        logger.info("🎭 Using MOCK mode")
                        file_path = await self.process_report_mock(task.articles)
                    else:
                        logger.info("🌐 Using REAL browser mode")
                        file_path = await self.process_report_real(task.articles)
                    
                    # Create success result
                    result = ReportResult(
                        task_id=task.task_id,
                        user_id=task.user_id,
                        chat_id=task.chat_id,
                        success=True,
                        file_path=file_path,
                        loading_message_id=task.loading_message_id
                    )
                    
                    logger.info(f"✅ Task {task.task_id} completed successfully")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing task {task.task_id}: {e}", exc_info=True)
                    result = ReportResult(
                        task_id=task.task_id,
                        user_id=task.user_id,
                        chat_id=task.chat_id,
                        success=False,
                        error=str(e),
                        loading_message_id=task.loading_message_id
                    )
                
                # Add result to result queue
                await self.report_queue.add_result(result)
                self.report_queue.task_done()
                
            except Exception as e:
                logger.error(f"❌ Queue worker error: {e}", exc_info=True)
                await asyncio.sleep(1)
        
        logger.info("🛑 Queue worker stopped")
    
    async def result_processor(self):
        """Process results and send to users"""
        logger.info("📤 Result processor started")
        
        while not self._shutdown:
            try:
                # Get result from queue (with timeout to check shutdown flag)
                try:
                    result: ReportResult = await asyncio.wait_for(
                        self.report_queue.get_result(),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                logger.info(f"📨 Processing result for task {result.task_id}")
                
                try:
                    # Delete loading sticker if it exists
                    if result.loading_message_id:
                        try:
                            await self.bot.delete_message(
                                chat_id=result.chat_id,
                                message_id=result.loading_message_id
                            )
                            logger.info(f"🗑️  Deleted loading sticker {result.loading_message_id}")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not delete loading sticker: {e}")
                    
                    if result.success:
                        # Send file
                        logger.info(f"📎 Sending file to chat {result.chat_id}")
                        
                        # Check file exists
                        if not os.path.exists(result.file_path):
                            raise FileNotFoundError(f"File not found: {result.file_path}")
                        
                        document = FSInputFile(result.file_path)
                        await self.bot.send_document(
                            chat_id=result.chat_id,
                            document=document,
                            caption="✅ <b>Отчет готов!</b>"
                        )
                        
                        # Delete file after sending
                        try:
                            os.unlink(result.file_path)
                            logger.info(f"🗑️  Deleted file: {result.file_path}")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not delete file: {e}")
                        
                        # Deduct balance
                        logger.info(f"💰 Deducting balance for user {result.user_id}")
                        await update_balance(result.user_id, -1)
                        
                        # Send balance info
                        balance = await check_balance(result.user_id)  # Get current balance
                        await self.bot.send_message(
                                chat_id=result.chat_id,
                                text=f"💰 Осталось отчетов: <b>{balance}</b>"
                            )
                    
                    else:
                        # Error occurred
                        logger.error(f"❌ Task {result.task_id} failed: {result.error}")
                        await self.bot.send_message(
                            chat_id=result.chat_id,
                            text=f"❌ <b>Ошибка при генерации отчета</b>\n\n"
                                 f"<code>{result.error}</code>\n\n"
                                 f"Баланс не был списан. Попробуйте позже."
                        )
                
                except Exception as e:
                    logger.error(f"❌ Error processing result {result.task_id}: {e}", exc_info=True)
            
            except Exception as e:
                logger.error(f"❌ Result processor error: {e}", exc_info=True)
                await asyncio.sleep(1)
        
        logger.info("🛑 Result processor stopped")
    
    async def ensure_wb_authorized(self):
        """
        Background task to ensure WB client is authorized.
        
        IMPORTANT: This runs AFTER bot polling starts to avoid deadlock.
        During authorization, the bot needs to receive and process auth codes
        from Telegram. If we check authorization during setup(), the bot
        won't be able to process messages yet, causing a deadlock.
        """
        try:
            # Wait for bot polling to fully start
            await asyncio.sleep(2)
            
            logger.info("🔐 Checking Wildberries authorization...")
            if self.wb_client and self.wb_client._auth_service:
                await self.wb_client._auth_service.ensure_authorized()
                logger.info("✅ Wildberries authorization check complete")
            else:
                logger.warning("⚠️ WB client not initialized")
        except Exception as e:
            logger.error(f"❌ Error checking WB authorization: {e}", exc_info=True)
    
    async def periodic_state_saver(self):
        """
        Background task to periodically save browser state.
        
        This ensures that browser sessions (cookies, tokens) are persisted
        regularly, reducing the need for re-authentication if the app restarts.
        """
        logger.info(f"💾 Periodic state saver started (interval: {settings.wb_state_save_interval}s)")
        
        while not self._shutdown:
            try:
                # Wait for the configured interval
                await asyncio.sleep(settings.wb_state_save_interval)
                
                # Save current browser state
                if self.wb_client:
                    await self.wb_client.save_current_state()
                else:
                    logger.warning("⚠️ WB client not initialized, skipping state save")
                    
            except asyncio.CancelledError:
                logger.info("🛑 Periodic state saver cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in periodic state saver: {e}", exc_info=True)
                # Continue running even if one save fails
                await asyncio.sleep(10)
        
        logger.info("🛑 Periodic state saver stopped")
    
    async def start(self):
        """Start the application"""
        # Setup components
        await self.setup()
        
        # Start queue worker
        logger.info("🚀 Starting queue worker...")
        self.worker_task = asyncio.create_task(self.queue_worker())
        
        # Start result processor
        logger.info("🚀 Starting result processor...")
        self.result_processor_task = asyncio.create_task(self.result_processor())
        
        # Start WB authorization check in background (after polling starts)
        logger.info("🚀 Scheduling WB authorization check...")
        self.auth_check_task = asyncio.create_task(self.ensure_wb_authorized())
        
        # Start periodic state saver
        logger.info("🚀 Starting periodic state saver...")
        self.state_saver_task = asyncio.create_task(self.periodic_state_saver())
        
        # Start bot polling
        logger.info("🎯 Starting bot polling...")
        try:
            # Skip pending updates to only process new ones
            await self.dp.start_polling(self.bot, skip_updates=True)
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the application"""
        logger.info("🛑 Shutting down...")
        self._shutdown = True
        
        # Wait for workers to finish
        if self.worker_task:
            logger.info("⏳ Waiting for queue worker...")
            await self.worker_task
        
        if self.result_processor_task:
            logger.info("⏳ Waiting for result processor...")
            await self.result_processor_task
        
        if self.auth_check_task:
            logger.info("⏳ Waiting for auth check task...")
            try:
                await asyncio.wait_for(self.auth_check_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("⚠️ Auth check task timeout, cancelling...")
                self.auth_check_task.cancel()
        
        if self.state_saver_task:
            logger.info("⏳ Stopping periodic state saver...")
            try:
                await asyncio.wait_for(self.state_saver_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("⚠️ State saver task timeout, cancelling...")
                self.state_saver_task.cancel()
                try:
                    await self.state_saver_task
                except asyncio.CancelledError:
                    pass
        
        # Save state one final time before disconnecting
        use_mock = await get_wb_use_mock()
        if self.wb_client and not use_mock:
            logger.info("💾 Saving final browser state before shutdown...")
            try:
                await self.wb_client.save_current_state()
            except Exception as e:
                logger.warning(f"⚠️ Could not save final state: {e}")
        
        # Disconnect browser
        if self.wb_client:
            logger.info("🔌 Disconnecting browser...")
            await self.wb_client.disconnect()
            logger.info("✅ Browser disconnected")
        
        # Close Supabase
        logger.info("📊 Closing Supabase client...")
        SupabaseClient.close()
        
        # Close bot
        if self.bot:
            await self.bot.session.close()
        
        logger.info("✅ Shutdown complete")


async def main():
    """Main entry point"""
    # Setup logging
    setup_logging()
    
    # Create and start application
    app = Application()
    await app.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Interrupted by user")
    except Exception as e:
        logger.exception(f"💥 Fatal error: {e}")
