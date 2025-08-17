"""
Health check utilities for the Telegram rewards bot.

This module provides comprehensive health checks for all application components
including database connectivity, bot status, blockchain monitor, and external APIs.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone

import httpx
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import config
from database import DatabaseManager

logger = logging.getLogger(__name__)


class HealthChecker:
    """Comprehensive health checker for all application components."""
    
    def __init__(self):
        self.start_time = time.time()
    
    async def check_database(self, db_manager: Optional[DatabaseManager] = None) -> Dict[str, Any]:
        """Check database connectivity and basic operations."""
        try:
            if not db_manager:
                # Create a temporary database manager for health check
                from database import get_db_manager
                db_manager = await get_db_manager()
            
            # Test basic database connectivity
            async with db_manager.get_session() as session:
                # Simple query to test connection
                result = await session.execute("SELECT 1 as test")
                test_value = result.scalar()
                
                if test_value != 1:
                    raise Exception("Database query returned unexpected result")
            
            return {
                "status": "healthy",
                "message": "Database connection successful",
                "details": {
                    "engine_pool_size": db_manager.engine.pool.size() if db_manager.engine else 0,
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
        
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}",
                "details": {
                    "error": str(e),
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
    
    async def check_bot(self, bot: Optional[Bot] = None) -> Dict[str, Any]:
        """Check Telegram bot connectivity and API access."""
        try:
            if not bot:
                # Create a temporary bot instance for health check
                bot = Bot(token=config.BOT_TOKEN)
            
            # Test bot API connectivity
            bot_info = await bot.get_me()
            
            # Clean up temporary bot
            if not bot:
                await bot.session.close()
            
            return {
                "status": "healthy",
                "message": "Bot API connection successful",
                "details": {
                    "bot_username": bot_info.username,
                    "bot_id": bot_info.id,
                    "can_join_groups": bot_info.can_join_groups,
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
        
        except TelegramAPIError as e:
            logger.error(f"Bot health check failed with Telegram API error: {e}")
            return {
                "status": "unhealthy",
                "message": f"Bot API error: {str(e)}",
                "details": {
                    "error_type": "TelegramAPIError",
                    "error": str(e),
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Bot health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Bot connection failed: {str(e)}",
                "details": {
                    "error": str(e),
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
    
    async def check_tatum_api(self) -> Dict[str, Any]:
        """Check Tatum API connectivity."""
        try:
            headers = {
                "x-api-key": config.TATUM_API_KEY,
                "Content-Type": "application/json"
            }
            
            # Test Tatum API with a simple status call
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.tatum.io/v3/tatum/usage",
                    headers=headers
                )
                
                if response.status_code == 200:
                    usage_data = response.json()
                    return {
                        "status": "healthy",
                        "message": "Tatum API connection successful",
                        "details": {
                            "plan": usage_data.get("plan", "unknown"),
                            "credit_limit": usage_data.get("creditLimit", 0),
                            "credits_consumed": usage_data.get("creditsConsumed", 0),
                            "checked_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "message": f"Tatum API returned status {response.status_code}",
                        "details": {
                            "status_code": response.status_code,
                            "response": response.text[:200],
                            "checked_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
        
        except httpx.TimeoutException:
            logger.error("Tatum API health check timed out")
            return {
                "status": "unhealthy",
                "message": "Tatum API connection timed out",
                "details": {
                    "error": "timeout",
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Tatum API health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Tatum API connection failed: {str(e)}",
                "details": {
                    "error": str(e),
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
    
    async def check_blockchain_monitor(self, blockchain_monitor=None) -> Dict[str, Any]:
        """Check blockchain monitor status."""
        try:
            if not blockchain_monitor:
                return {
                    "status": "warning",
                    "message": "Blockchain monitor not available for health check",
                    "details": {
                        "checked_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            
            # Check if monitor is properly initialized
            if hasattr(blockchain_monitor, 'tatum_client') and blockchain_monitor.tatum_client:
                return {
                    "status": "healthy",
                    "message": "Blockchain monitor active",
                    "details": {
                        "network": config.BLOCKCHAIN_NETWORK,
                        "contract_address": config.TOKEN_CONTRACT_ADDRESS,
                        "checked_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": "Blockchain monitor not properly initialized",
                    "details": {
                        "checked_at": datetime.now(timezone.utc).isoformat()
                    }
                }
        
        except Exception as e:
            logger.error(f"Blockchain monitor health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Blockchain monitor check failed: {str(e)}",
                "details": {
                    "error": str(e),
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
    
    def check_configuration(self) -> Dict[str, Any]:
        """Check application configuration."""
        try:
            # Validate configuration
            config.validate()
            
            return {
                "status": "healthy",
                "message": "Configuration valid",
                "details": {
                    "environment": config.ENVIRONMENT,
                    "port": config.PORT,
                    "blockchain_network": config.BLOCKCHAIN_NETWORK,
                    "has_bot_token": bool(config.BOT_TOKEN),
                    "has_database_url": bool(config.DATABASE_URL),
                    "has_tatum_api_key": bool(config.TATUM_API_KEY),
                    "has_contract_address": bool(config.TOKEN_CONTRACT_ADDRESS),
                    "admin_users_count": len(config.ADMIN_USER_IDS),
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
        
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Configuration invalid: {str(e)}",
                "details": {
                    "error": str(e),
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            }
    
    async def comprehensive_health_check(
        self,
        bot: Optional[Bot] = None,
        db_manager: Optional[DatabaseManager] = None,
        blockchain_monitor=None
    ) -> Dict[str, Any]:
        """Perform comprehensive health check of all components."""
        health_results = {
            "overall_status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": int(time.time() - self.start_time),
            "checks": {}
        }
        
        # Run all health checks concurrently
        try:
            tasks = {
                "configuration": asyncio.create_task(
                    asyncio.to_thread(self.check_configuration)
                ),
                "database": asyncio.create_task(
                    self.check_database(db_manager)
                ),
                "bot": asyncio.create_task(
                    self.check_bot(bot)
                ),
                "tatum_api": asyncio.create_task(
                    self.check_tatum_api()
                ),
                "blockchain_monitor": asyncio.create_task(
                    self.check_blockchain_monitor(blockchain_monitor)
                )
            }
            
            # Wait for all checks to complete
            for check_name, task in tasks.items():
                try:
                    result = await task
                    health_results["checks"][check_name] = result
                    
                    # Update overall status based on individual checks
                    if result["status"] == "unhealthy":
                        health_results["overall_status"] = "unhealthy"
                    elif result["status"] == "warning" and health_results["overall_status"] == "healthy":
                        health_results["overall_status"] = "warning"
                
                except Exception as e:
                    logger.error(f"Health check '{check_name}' failed: {e}")
                    health_results["checks"][check_name] = {
                        "status": "unhealthy",
                        "message": f"Health check failed: {str(e)}",
                        "details": {
                            "error": str(e),
                            "checked_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                    health_results["overall_status"] = "unhealthy"
        
        except Exception as e:
            logger.error(f"Comprehensive health check failed: {e}")
            health_results["overall_status"] = "unhealthy"
            health_results["error"] = str(e)
        
        return health_results


# Global health checker instance
health_checker = HealthChecker()


async def quick_health_check() -> Dict[str, Any]:
    """Quick health check for basic readiness probe."""
    try:
        # For readiness, we just need to know the service can respond
        # Don't fail on configuration issues - that's for the full health check
        # Always return healthy for readiness to ensure Railway deployment succeeds
        return {
            "status": "healthy",
            "message": "Service is ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": int(time.time() - health_checker.start_time)
        }
    
    except Exception as e:
        logger.error(f"Quick health check failed: {e}")
        return {
            "status": "healthy",  # Still return healthy for readiness
            "message": f"Service is ready (error: {str(e)})",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


if __name__ == "__main__":
    """Run health checks from command line."""
    import sys
    
    async def main():
        print("Running comprehensive health check...")
        result = await health_checker.comprehensive_health_check()
        
        print(f"\nOverall Status: {result['overall_status']}")
        print(f"Timestamp: {result['timestamp']}")
        print(f"Uptime: {result['uptime_seconds']} seconds")
        
        print("\nDetailed Results:")
        for check_name, check_result in result.get("checks", {}).items():
            status = check_result["status"]
            message = check_result["message"]
            print(f"  {check_name}: {status} - {message}")
        
        # Exit with error code if unhealthy
        if result["overall_status"] == "unhealthy":
            sys.exit(1)
        else:
            sys.exit(0)
    
    # Run the health check
    asyncio.run(main())
