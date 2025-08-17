"""Main application entry point."""

import asyncio
import logging
import sys
import signal
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot import create_bot, create_dispatcher
from database import get_db_manager
from blockchain import BlockchainMonitor
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Global instances
bot: Bot = None
dp: Dispatcher = None
db_manager = None
blockchain_monitor = None


@asynccontextmanager
async def lifespan_context():
    """Context manager for application lifespan."""
    global bot, dp, db_manager, blockchain_monitor
    
    try:
        # Validate configuration
        config.validate()
        logger.info("Configuration validated successfully")
        
        # Initialize database
        db_manager = await get_db_manager()
        logger.info("Database initialized successfully")
        
        # Initialize blockchain monitor
        blockchain_monitor = BlockchainMonitor()
        await blockchain_monitor.initialize()
        logger.info("Blockchain monitor initialized successfully")
        
        # Create bot and dispatcher
        bot = create_bot()
        dp = await create_dispatcher()
        logger.info("Bot and dispatcher created successfully")
        
        # Start blockchain monitoring in background
        monitoring_task = asyncio.create_task(
            blockchain_monitor.start_monitoring(interval_seconds=300)  # 5 minutes
        )
        logger.info("Blockchain monitoring started")
        
        yield {
            'bot': bot,
            'dp': dp,
            'db_manager': db_manager,
            'blockchain_monitor': blockchain_monitor,
            'monitoring_task': monitoring_task
        }
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Cleanup
        if blockchain_monitor:
            await blockchain_monitor.close()
        
        if db_manager:
            await db_manager.close()
        
        if bot:
            await bot.session.close()
        
        logger.info("Application shutdown completed")


async def webhook_handler(request):
    """Handle webhook requests."""
    try:
        # Get bot and dispatcher from app context
        bot = request.app['bot']
        dp = request.app['dp']
        
        # Create request handler
        handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        
        # Process the webhook
        return await handler.handle(request)
        
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return web.Response(status=500)


async def health_check(request):
    """Health check endpoint."""
    is_ready = request.app.get('is_ready', False)
    return web.json_response({
        'status': 'ok',
        'ready': is_ready,
        'timestamp': str(datetime.now(timezone.utc))
    })


async def test_endpoint(request):
    """Simple test endpoint to verify server is running."""
    return web.json_response({
        'message': 'Server is running',
        'timestamp': str(datetime.now(timezone.utc))
    })


def create_app():
    """Create and configure the web application."""
    app = web.Application()
    
    # Add health check endpoint
    app.router.add_get('/health', health_check)
    
    # Add test endpoint
    app.router.add_get('/test', test_endpoint)
    
    # Add webhook endpoint
    app.router.add_post('/webhook', webhook_handler)
    
    return app


async def run_polling():
    """Run bot in polling mode (for development)."""
    async with lifespan_context() as context:
        bot = context['bot']
        dp = context['dp']
        
        logger.info("Starting bot in polling mode...")
        
        # Delete webhook
        await bot.delete_webhook(drop_pending_updates=True)
        
        try:
            await dp.start_polling(bot)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Error in polling mode: {e}")
            raise


async def run_webhook():
    """Run bot in webhook mode (for production)."""
    # Create web application and start server FIRST so /health is available immediately
    app = create_app()
    app['is_ready'] = False

    logger.info("Starting web server (health endpoint available immediately)...")

    try:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', config.PORT)
        await site.start()
        logger.info(f"Web server started successfully on port {config.PORT}")
        logger.info("Health endpoint /health is now accessible")
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")
        raise

    async def initialize_services():
        """Initialize dependencies without blocking health endpoint."""
        try:
            # Validate configuration
            config.validate()

            # Initialize database
            db_manager_local = await get_db_manager()
            app['db_manager'] = db_manager_local

            # Initialize blockchain monitor
            blockchain_monitor_local = BlockchainMonitor()
            await blockchain_monitor_local.initialize()
            app['blockchain_monitor'] = blockchain_monitor_local

            # Create bot and dispatcher
            bot_local = create_bot()
            dp_local = await create_dispatcher()
            app['bot'] = bot_local
            app['dp'] = dp_local

            # Start blockchain monitoring in background
            app['monitoring_task'] = asyncio.create_task(
                blockchain_monitor_local.start_monitoring(interval_seconds=300)
            )

            # Set webhook (configure with your Railway public URL)
            webhook_url = f"https://your-railway-app-url.railway.app/webhook"
            try:
                await bot_local.set_webhook(webhook_url)
                logger.info(f"Webhook set to: {webhook_url}")
            except Exception as e:
                logger.warning(f"Could not set webhook: {e}")
                logger.info("Continuing without webhook (polling fallback if enabled)")

            # Mark app as ready
            app['is_ready'] = True
            logger.info("Service initialization completed; app is ready")

        except Exception as e:
            # Keep server running for health endpoint even if initialization fails
            app['is_ready'] = False
            logger.error(f"Service initialization failed: {e}")

    async def shutdown_services():
        """Cleanup resources on shutdown."""
        try:
            monitoring_task = app.get('monitoring_task')
            if monitoring_task:
                monitoring_task.cancel()
            blockchain_monitor_local = app.get('blockchain_monitor')
            if blockchain_monitor_local:
                await blockchain_monitor_local.close()
            db_manager_local = app.get('db_manager')
            if db_manager_local:
                await db_manager_local.close()
            bot_local = app.get('bot')
            if bot_local:
                await bot_local.session.close()
        except Exception as e:
            logger.warning(f"Error during shutdown: {e}")

    # Kick off initialization in the background
    asyncio.create_task(initialize_services())

    try:
        # Keep the server running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    finally:
        await shutdown_services()
        await runner.cleanup()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main application entry point."""
    try:
        setup_signal_handlers()
        
        # Choose mode based on environment
        if config.ENVIRONMENT == "development":
            logger.info("Running in development mode (polling)")
            await run_polling()
        else:
            logger.info("Running in production mode (webhook)")
            await run_webhook()
            
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
