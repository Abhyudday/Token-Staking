"""Main application entry point.

Health Check Endpoints:
- /health - Comprehensive health check of all components (database, bot, APIs, etc.)
- /ready - Quick readiness check for container startup
- /healthz - Kubernetes-style readiness probe (same as /ready)

The health check endpoints return:
- HTTP 200 when healthy
- HTTP 503 when unhealthy
- JSON response with detailed status information
"""

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
from healthcheck import health_checker, quick_health_check

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
        try:
            config.validate()
            logger.info("Configuration validated successfully")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
        
        # Initialize database
        try:
            db_manager = await get_db_manager()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
        
        # Initialize blockchain monitor
        try:
            blockchain_monitor = BlockchainMonitor()
            await blockchain_monitor.initialize()
            logger.info("Blockchain monitor initialized successfully")
        except Exception as e:
            logger.error(f"Blockchain monitor initialization failed: {e}")
            # Don't fail startup for blockchain monitor issues
            blockchain_monitor = None
        
        # Create bot and dispatcher
        try:
            bot = create_bot()
            dp = await create_dispatcher()
            logger.info("Bot and dispatcher created successfully")
        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            raise
        
        # Start blockchain monitoring in background if available
        monitoring_task = None
        if blockchain_monitor:
            try:
                monitoring_task = asyncio.create_task(
                    blockchain_monitor.start_monitoring(interval_seconds=300)  # 5 minutes
                )
                logger.info("Blockchain monitoring started")
            except Exception as e:
                logger.warning(f"Failed to start blockchain monitoring: {e}")
                monitoring_task = None
        
        logger.info("Application initialization completed successfully")
        
        yield {
            'bot': bot,
            'dp': dp,
            'db_manager': db_manager,
            'blockchain_monitor': blockchain_monitor,
            'monitoring_task': monitoring_task
        }
        
    except Exception as e:
        logger.error(f"Critical error during startup: {e}")
        raise
    finally:
        # Cleanup
        try:
            if blockchain_monitor:
                await blockchain_monitor.close()
            
            if db_manager:
                await db_manager.close()
            
            if bot:
                await bot.session.close()
            
            logger.info("Application shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


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
    """Health check endpoint with real status checks."""
    try:
        # Get application context
        bot = request.app.get('bot')
        db_manager = request.app.get('db_manager')
        blockchain_monitor = request.app.get('blockchain_monitor')
        
        # Perform comprehensive health check
        health_result = await health_checker.comprehensive_health_check(
            bot=bot,
            db_manager=db_manager,
            blockchain_monitor=blockchain_monitor
        )
        
        # Return appropriate HTTP status based on health
        status_code = 200 if health_result['overall_status'] == 'healthy' else 503
        
        return web.json_response(health_result, status=status_code)
        
    except Exception as e:
        logger.error(f"Health check endpoint failed: {e}")
        return web.json_response({
            'status': 'unhealthy',
            'message': f'Health check failed: {str(e)}',
            'timestamp': None
        }, status=503)


async def readiness_check(request):
    """Readiness check endpoint for quick probes."""
    try:
        # Quick health check for readiness
        health_result = await quick_health_check()
        
        # Return appropriate HTTP status
        status_code = 200 if health_result['status'] == 'healthy' else 503
        
        return web.json_response(health_result, status=status_code)
        
    except Exception as e:
        logger.error(f"Readiness check endpoint failed: {e}")
        return web.json_response({
            'status': 'unhealthy',
            'message': f'Readiness check failed: {str(e)}'
        }, status=503)


async def create_app():
    """Create and configure the web application."""
    app = web.Application()
    
    # Add startup health check (responds immediately)
    async def startup_check(request):
        """Startup check - responds immediately when server is running."""
        return web.json_response({
            'status': 'starting',
            'message': 'Server is starting up',
            'timestamp': None
        })
    
    # Add health check endpoints
    app.router.add_get('/', startup_check)  # Root endpoint for basic connectivity
    app.router.add_get('/health', health_check)
    app.router.add_get('/ready', readiness_check)
    app.router.add_get('/healthz', readiness_check)  # Common Kubernetes readiness probe path
    
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
        
        # Try to set webhook if RAILWAY_PUBLIC_DOMAIN is available
        webhook_url = None
        if hasattr(config, 'RAILWAY_PUBLIC_DOMAIN') and config.RAILWAY_PUBLIC_DOMAIN:
            webhook_url = f"https://{config.RAILWAY_PUBLIC_DOMAIN}/webhook"
            try:
                await bot.set_webhook(webhook_url)
                logger.info(f"Webhook set to: {webhook_url}")
            except Exception as e:
                logger.warning(f"Could not set webhook: {e}")
                webhook_url = None
        
        if not webhook_url:
            logger.info("Running without webhook (webhook not configured)")
        
        # Start web server
        try:
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, '0.0.0.0', config.PORT)
            await site.start()
            
            logger.info(f"Web server started on port {config.PORT}")
            logger.info("Health check endpoints available at:")
            logger.info(f"  - http://0.0.0.0:{config.PORT}/health")
            logger.info(f"  - http://0.0.0.0:{config.PORT}/ready")
            logger.info(f"  - http://0.0.0.0:{config.PORT}/healthz")
            
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")
            raise
        
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
