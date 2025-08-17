"""Main application entry point."""

import asyncio
import logging
import sys
import signal
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

# Configure basic logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global flag to track if full app is ready
app_ready = False

async def health_check(request):
    """Health check endpoint - always available."""
    global app_ready
    return web.json_response({
        'status': 'ok',
        'ready': app_ready,
        'timestamp': str(datetime.now(timezone.utc)),
        'message': 'Health endpoint is working'
    })

async def test_endpoint(request):
    """Simple test endpoint to verify server is running."""
    return web.json_response({
        'message': 'Server is running',
        'timestamp': str(datetime.now(timezone.utc))
    })

def create_minimal_app():
    """Create minimal web application with just health endpoints."""
    from aiohttp import web
    
    app = web.Application()
    
    # Add health check endpoint
    app.router.add_get('/health', health_check)
    
    # Add test endpoint
    app.router.add_get('/test', test_endpoint)
    
    return app

async def start_minimal_server():
    """Start minimal web server immediately."""
    from aiohttp import web
    from config import config
    
    try:
        app = create_minimal_app()
        
        logger.info("Starting minimal web server...")
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        # Try to get port from environment, fallback to 8000
        port = int(os.getenv("PORT", "8000"))
        
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"Minimal web server started successfully on port {port}")
        logger.info("Health endpoint /health is now accessible")
        
        return runner, site
        
    except Exception as e:
        logger.error(f"Failed to start minimal web server: {e}")
        raise

async def initialize_full_app():
    """Initialize the full application in the background."""
    global app_ready
    
    try:
        logger.info("Starting full application initialization...")
        
        # Import dependencies only when needed
        from aiogram import Bot, Dispatcher
        from bot import create_bot, create_dispatcher
        from database import get_db_manager
        from blockchain import BlockchainMonitor
        from config import config
        
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
            blockchain_monitor.start_monitoring(interval_seconds=300)
        )
        logger.info("Blockchain monitoring started")
        
        # Mark app as ready
        app_ready = True
        logger.info("Full application initialization completed successfully")
        
        return {
            'bot': bot,
            'dp': dp,
            'db_manager': db_manager,
            'blockchain_monitor': blockchain_monitor,
            'monitoring_task': monitoring_task
        }
        
    except Exception as e:
        logger.error(f"Full application initialization failed: {e}")
        app_ready = False
        return None

async def main():
    """Main application entry point."""
    try:
        # Start minimal server immediately
        runner, site = await start_minimal_server()
        
        # Initialize full app in background
        init_task = asyncio.create_task(initialize_full_app())
        
        # Keep the server running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            # Cleanup
            init_task.cancel()
            await runner.cleanup()
            
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
