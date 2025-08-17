"""Health check module for the Telegram rewards bot."""

import asyncio
import logging
import aiohttp
from aiohttp import web
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class HealthChecker:
    """Health checker for application services."""
    
    def __init__(self):
        self.db_manager = None
        self.blockchain_monitor = None
        self.bot = None
        self.dp = None
    
    def set_services(self, db_manager=None, blockchain_monitor=None, bot=None, dp=None):
        """Set service references for health checking."""
        self.db_manager = db_manager
        self.blockchain_monitor = blockchain_monitor
        self.bot = bot
        self.dp = dp
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            if self.db_manager:
                # Try to execute a simple query
                async with self.db_manager.get_session() as session:
                    await session.execute("SELECT 1")
                return {"status": "healthy", "message": "Database connection successful"}
            else:
                return {"status": "unhealthy", "message": "Database manager not initialized"}
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"status": "unhealthy", "message": f"Database error: {str(e)}"}
    
    async def check_blockchain_monitor(self) -> Dict[str, Any]:
        """Check blockchain monitor status."""
        try:
            if self.blockchain_monitor:
                # Check if the monitor is active
                if hasattr(self.blockchain_monitor, 'is_running'):
                    is_running = self.blockchain_monitor.is_running
                else:
                    is_running = True  # Assume running if we can't check
                
                if is_running:
                    return {"status": "healthy", "message": "Blockchain monitor is active"}
                else:
                    return {"status": "unhealthy", "message": "Blockchain monitor is not running"}
            else:
                return {"status": "unhealthy", "message": "Blockchain monitor not initialized"}
        except Exception as e:
            logger.error(f"Blockchain monitor health check failed: {e}")
            return {"status": "unhealthy", "message": f"Blockchain monitor error: {str(e)}"}
    
    async def check_bot(self) -> Dict[str, Any]:
        """Check bot status."""
        try:
            if self.bot:
                # Try to get bot info
                bot_info = await self.bot.get_me()
                return {
                    "status": "healthy", 
                    "message": "Bot is running",
                    "bot_id": bot_info.id,
                    "bot_username": bot_info.username
                }
            else:
                return {"status": "unhealthy", "message": "Bot not initialized"}
        except Exception as e:
            logger.error(f"Bot health check failed: {e}")
            return {"status": "unhealthy", "message": f"Bot error: {str(e)}"}
    
    async def check_dispatcher(self) -> Dict[str, Any]:
        """Check dispatcher status."""
        try:
            if self.dp:
                return {"status": "healthy", "message": "Dispatcher is running"}
            else:
                return {"status": "unhealthy", "message": "Dispatcher not initialized"}
        except Exception as e:
            logger.error(f"Dispatcher health check failed: {e}")
            return {"status": "unhealthy", "message": f"Dispatcher error: {str(e)}"}
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            # Run all health checks concurrently
            db_check, blockchain_check, bot_check, dispatcher_check = await asyncio.gather(
                self.check_database(),
                self.check_blockchain_monitor(),
                self.check_bot(),
                self.check_dispatcher(),
                return_exceptions=True
            )
            
            # Handle any exceptions from health checks
            if isinstance(db_check, Exception):
                db_check = {"status": "unhealthy", "message": f"Database check error: {str(db_check)}"}
            if isinstance(blockchain_check, Exception):
                blockchain_check = {"status": "unhealthy", "message": f"Blockchain check error: {str(blockchain_check)}"}
            if isinstance(bot_check, Exception):
                bot_check = {"status": "unhealthy", "message": f"Bot check error: {str(bot_check)}"}
            if isinstance(dispatcher_check, Exception):
                dispatcher_check = {"status": "unhealthy", "message": f"Dispatcher check error: {str(dispatcher_check)}"}
            
            # Determine overall health
            all_checks = [db_check, blockchain_check, bot_check, dispatcher_check]
            overall_status = "healthy" if all(check["status"] == "healthy" for check in all_checks) else "unhealthy"
            
            # Calculate HTTP status code
            http_status = 200 if overall_status == "healthy" else 503
            
            return {
                "status": overall_status,
                "timestamp": asyncio.get_event_loop().time(),
                "services": {
                    "database": db_check,
                    "blockchain_monitor": blockchain_check,
                    "bot": bot_check,
                    "dispatcher": dispatcher_check
                },
                "http_status": http_status
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "timestamp": asyncio.get_event_loop().time(),
                "error": str(e),
                "http_status": 500
            }


# Global health checker instance
health_checker = HealthChecker()


async def health_check_handler(request):
    """HTTP handler for health check endpoint."""
    try:
        # Perform health check
        health_result = await health_checker.perform_health_check()
        
        # Set appropriate HTTP status
        status = health_result.get("http_status", 200)
        
        # Return JSON response
        return web.json_response(
            health_result,
            status=status,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )
        
    except Exception as e:
        logger.error(f"Health check handler error: {e}")
        return web.json_response(
            {
                "status": "unhealthy",
                "error": "Health check failed",
                "message": str(e)
            },
            status=500
        )


async def simple_health_check(request):
    """Simple health check that just returns OK."""
    return web.Response(
        text="OK",
        status=200,
        headers={
            "Content-Type": "text/plain",
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )


async def readiness_check(request):
    """Readiness check that verifies the application is ready to serve requests."""
    try:
        # Check if basic services are available
        if health_checker.db_manager and health_checker.bot:
            return web.Response(
                text="READY",
                status=200,
                headers={
                    "Content-Type": "text/plain",
                    "Cache-Control": "no-cache, no-store, must-revalidate"
                }
            )
        else:
            return web.Response(
                text="NOT_READY",
                status=503,
                headers={
                    "Content-Type": "text/plain",
                    "Cache-Control": "no-cache, no-store, must-revalidate"
                }
            )
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return web.Response(
            text="NOT_READY",
            status=503,
            headers={
                "Content-Type": "text/plain",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )


def setup_health_routes(app: web.Application):
    """Setup health check routes on the application."""
    app.router.add_get('/health', health_check_handler)
    app.router.add_get('/health/simple', simple_health_check)
    app.router.add_get('/health/ready', readiness_check)
    app.router.add_get('/', simple_health_check)  # Root endpoint also serves as health check


def set_health_checker_services(db_manager=None, blockchain_monitor=None, bot=None, dp=None):
    """Set services for the global health checker."""
    health_checker.set_services(db_manager, blockchain_monitor, bot, dp)
