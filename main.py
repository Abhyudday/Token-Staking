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
    """Health check endpoint with comprehensive status checks."""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': asyncio.get_event_loop().time(),
            'checks': {}
        }
        
        # Check bot status
        try:
            bot = request.app.get('bot')
            if bot and hasattr(bot, 'session') and not bot.session.closed:
                # Try a simple API call to verify bot connectivity
                me = await bot.get_me()
                health_status['checks']['bot'] = {
                    'status': 'healthy',
                    'username': me.username,
                    'message': 'Bot is connected and responsive'
                }
            else:
                health_status['checks']['bot'] = {
                    'status': 'unhealthy',
                    'message': 'Bot instance not available or session closed'
                }
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['checks']['bot'] = {
                'status': 'unhealthy',
                'message': f'Bot check failed: {str(e)}'
            }
            health_status['status'] = 'degraded'
        
        # Check database status
        try:
            db_manager = request.app.get('db_manager')
            if db_manager:
                # Perform a simple database connectivity check
                await db_manager.ping()
                health_status['checks']['database'] = {
                    'status': 'healthy',
                    'message': 'Database connection is active'
                }
            else:
                health_status['checks']['database'] = {
                    'status': 'unhealthy',
                    'message': 'Database manager not available'
                }
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['checks']['database'] = {
                'status': 'unhealthy',
                'message': f'Database check failed: {str(e)}'
            }
            health_status['status'] = 'degraded'
        
        # Check blockchain monitor status
        try:
            blockchain_monitor = request.app.get('blockchain_monitor')
            if blockchain_monitor:
                health_status['checks']['blockchain_monitor'] = {
                    'status': 'healthy',
                    'message': 'Blockchain monitor is active'
                }
            else:
                health_status['checks']['blockchain_monitor'] = {
                    'status': 'unhealthy',
                    'message': 'Blockchain monitor not available'
                }
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['checks']['blockchain_monitor'] = {
                'status': 'unhealthy',
                'message': f'Blockchain monitor check failed: {str(e)}'
            }
            health_status['status'] = 'degraded'
        
        # Determine HTTP status code based on health
        if health_status['status'] == 'healthy':
            http_status = 200
        elif health_status['status'] == 'degraded':
            http_status = 200  # Still return 200 for degraded but functional
        else:
            http_status = 503  # Service Unavailable
            
        return web.json_response(health_status, status=http_status)
        
    except Exception as e:
        logger.error(f"Health check endpoint error: {e}")
        return web.json_response({
            'status': 'unhealthy',
            'message': f'Health check failed: {str(e)}',
            'timestamp': asyncio.get_event_loop().time()
        }, status=503)


async def create_app():
    """Create and configure the web application."""
    app = web.Application()
    
    # Add health check endpoint
    app.router.add_get('/health', health_check)
    
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
    async with lifespan_context() as context:
        bot = context['bot']
        dp = context['dp']
        monitoring_task = context['monitoring_task']
        
        # Create web application
        app = await create_app()
        
        # Store bot, dispatcher, and other components in app context
        app['bot'] = bot
        app['dp'] = dp
        app['db_manager'] = context['db_manager']
        app['blockchain_monitor'] = context['blockchain_monitor']
        
        logger.info("Starting bot in webhook mode...")
        
        # Set webhook (you'll need to configure this with your Railway URL)
        webhook_url = f"https://your-railway-app-url.railway.app/webhook"
        
        try:
            await bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
        except Exception as e:
            logger.warning(f"Could not set webhook: {e}")
            logger.info("Running without webhook (polling fallback)")
        
        # Start web server
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', config.PORT)
        await site.start()
        
        logger.info(f"Web server started on port {config.PORT}")
        
        try:
            # Keep the server running
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            monitoring_task.cancel()
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
