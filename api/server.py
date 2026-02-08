"""aiohttp web server for webhook endpoints"""
import logging
from aiohttp import web
from aiogram import Bot

from payment.webhook import handle_yookassa_webhook
from payment.payment_service import PaymentService

logger = logging.getLogger(__name__)


async def yookassa_webhook_handler(request: web.Request) -> web.Response:
    """
    Handle POST /api/payment/yookassa webhook from YooKassa
    
    Args:
        request: aiohttp request with JSON payload
        
    Returns:
        JSON response with status "ok"
    """
    try:
        # Parse JSON payload
        data = await request.json()
        
        # Get payment_service from app context
        payment_service = request.app['payment_service']
        
        # Process webhook
        result = await handle_yookassa_webhook(data, payment_service)
        
        # Always return 200 OK (even if processing failed)
        return web.json_response(result, status=200)
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Error in webhook handler: {e}", exc_info=True)
        # Still return 200 to prevent YooKassa retries
        return web.json_response({"status": "ok", "error": str(e)}, status=200)


async def health_check_handler(request: web.Request) -> web.Response:
    """
    Handle GET /health for health checks
    
    Returns:
        JSON response with status "ok"
    """
    return web.json_response({"status": "ok", "service": "card-compare-webhook"})


def create_app(bot: Bot) -> web.Application:
    """
    Create and configure aiohttp application
    
    Args:
        bot: Aiogram Bot instance for sending notifications
        
    Returns:
        Configured aiohttp Application
    """
    app = web.Application()
    
    # Initialize payment service with bot
    payment_service = PaymentService(bot=bot)
    app['payment_service'] = payment_service
    
    # Register routes
    app.router.add_post('/api/payment/yookassa', yookassa_webhook_handler)
    app.router.add_get('/health', health_check_handler)
    
    logger.info("✅ Web application created with routes:")
    logger.info("  - POST /api/payment/yookassa (YooKassa webhook)")
    logger.info("  - GET /health (health check)")
    
    return app


async def start_webhook_server(bot: Bot, host: str, port: int) -> web.AppRunner:
    """
    Start aiohttp webhook server
    
    Args:
        bot: Aiogram Bot instance
        host: Host to bind (e.g., '0.0.0.0')
        port: Port to listen on (e.g., 8080)
        
    Returns:
        AppRunner instance (needed for cleanup)
    """
    app = create_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info(f"🌐 Webhook server started on {host}:{port}")
    logger.info(f"   Webhook URL: http://{host}:{port}/api/payment/yookassa")
    
    return runner


async def stop_webhook_server(runner: web.AppRunner) -> None:
    """
    Stop aiohttp webhook server
    
    Args:
        runner: AppRunner instance from start_webhook_server
    """
    logger.info("🛑 Stopping webhook server...")
    await runner.cleanup()
    logger.info("✅ Webhook server stopped")
