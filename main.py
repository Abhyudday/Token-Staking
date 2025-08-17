"""Main application entry point."""

import asyncio
import logging
import sys
import signal
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
        logger.info("Starting application initialization...")
        
        # Validate configuration
        config.validate()
        logger.info("Configuration validated successfully")
        
        # Initialize database
        logger.info("Initializing database...")
        db_manager = await get_db_manager()
        await db_manager.initialize()
        logger.info("Database initialized successfully")
        
        # Initialize blockchain monitor
        logger.info("Initializing blockchain monitor...")
        blockchain_monitor = BlockchainMonitor()
        await blockchain_monitor.initialize()
        logger.info("Blockchain monitor initialized successfully")
        
        # Create bot and dispatcher
        logger.info("Creating bot and dispatcher...")
        bot = create_bot()
        dp = await create_dispatcher()
        logger.info("Bot and dispatcher created successfully")
        
        # Start blockchain monitoring in background
        logger.info("Starting blockchain monitoring...")
        monitoring_task = asyncio.create_task(
            blockchain_monitor.start_monitoring(interval_seconds=300)  # 5 minutes
        )
        logger.info("Blockchain monitoring started")
        
        logger.info("Application initialization completed successfully")
        
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
        logger.info("Starting application cleanup...")
        
        try:
            if blockchain_monitor:
                await blockchain_monitor.close()
                logger.info("Blockchain monitor closed")
        except Exception as e:
            logger.error(f"Error closing blockchain monitor: {e}")
        
        try:
            if db_manager:
                await db_manager.close()
                logger.info("Database manager closed")
        except Exception as e:
            logger.error(f"Error closing database manager: {e}")
        
        try:
            if bot:
                await bot.session.close()
                logger.info("Bot session closed")
        except Exception as e:
            logger.error(f"Error closing bot session: {e}")
        
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
    try:
        # Check if bot is running
        bot_status = 'running' if bot and not bot.session.closed else 'stopped'
        
        # Check database connection
        db_status = 'connected'
        if db_manager:
            try:
                # Try to get a database session to test connection
                async with db_manager.get_session() as session:
                    # Test with a simple query
                    result = await session.execute("SELECT 1")
                    await result.fetchone()
            except Exception as e:
                logger.warning(f"Database health check failed: {e}")
                db_status = 'disconnected'
        else:
            db_status = 'not_initialized'
        
        # Check blockchain monitor
        blockchain_status = 'active'
        if blockchain_monitor:
            try:
                # Simple check if monitor exists
                blockchain_status = 'active'
            except Exception as e:
                logger.warning(f"Blockchain monitor health check failed: {e}")
                blockchain_status = 'error'
        else:
            blockchain_status = 'not_initialized'
        
        # Determine overall health
        overall_status = 'healthy'
        if db_status == 'disconnected' or bot_status == 'stopped':
            overall_status = 'unhealthy'
        
        health_data = {
            'status': overall_status,
            'bot': bot_status,
            'database': db_status,
            'blockchain_monitor': blockchain_status,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        logger.info(f"Health check result: {health_data}")
        return web.json_response(health_data)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return web.json_response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': asyncio.get_event_loop().time()
        }, status=500)


async def create_app():
    """Create and configure the web application."""
    app = web.Application()
    
    # Add health check endpoint
    app.router.add_get('/health', health_check)
    
    # Add startup endpoint for debugging
    app.router.add_get('/', lambda r: web.json_response({'status': 'running', 'message': 'Telegram Bot API Server'}))
    
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
    try:
        async with lifespan_context() as context:
            bot = context['bot']
            dp = context['dp']
            monitoring_task = context['monitoring_task']
            
            # Create web application
            app = await create_app()
            
            # Store bot and dispatcher in app context
            app['bot'] = bot
            app['dp'] = dp
            
            logger.info("Starting bot in webhook mode...")
        
        # Set webhook - Railway will provide the PORT environment variable
        # For now, we'll skip setting the webhook and let Railway handle it
        # The webhook can be set manually through the Telegram Bot API
        logger.info("Skipping webhook setup - configure manually through Telegram Bot API")
        webhook_url = None
        
        if webhook_url:
            try:
                await bot.set_webhook(webhook_url)
                logger.info(f"Webhook set to: {webhook_url}")
            except Exception as e:
                logger.warning(f"Could not set webhook: {e}")
                logger.info("Running without webhook (polling fallback)")
        else:
            logger.info("No webhook URL configured, running without webhook")
        
        # Start web server
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', config.PORT)
        await site.start()
        
        logger.info(f"Web server started on port {config.PORT}")
        logger.info(f"Health check available at: http://0.0.0.0:{config.PORT}/health")
        logger.info(f"Root endpoint available at: http://0.0.0.0:{config.PORT}/")
        
        # Add a small delay to ensure all services are ready
        logger.info("Waiting 5 seconds for services to stabilize...")
        await asyncio.sleep(5)
        logger.info("Services stabilized, ready to accept requests")
        
        try:
            # Keep the server running
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            monitoring_task.cancel()
            await runner.cleanup()
    except Exception as e:
        logger.error(f"Error in webhook mode: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


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
        
        # Validate configuration first
        try:
            config.validate()
            logger.info("Configuration validated successfully")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            sys.exit(1)
        
        # Choose mode based on environment
        if config.ENVIRONMENT == "development":
            logger.info("Running in development mode (polling)")
            await run_polling()
        else:
            logger.info("Running in production mode (webhook)")
            await run_webhook()
            
    except Exception as e:
        logger.error(f"Application error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
