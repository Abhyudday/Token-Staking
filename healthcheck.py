#!/usr/bin/env python3
"""
Standalone health check script for Railway deployment.
This can be used as an alternative health check method.
"""

import asyncio
import aiohttp
import sys
import os
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_health_endpoint(url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Check the health endpoint of the application.
    
    Args:
        url: The health endpoint URL
        timeout: Request timeout in seconds
        
    Returns:
        Dict containing health check results
    """
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'status': 'healthy',
                        'http_status': response.status,
                        'response_data': data,
                        'message': 'Health check passed'
                    }
                else:
                    return {
                        'status': 'unhealthy',
                        'http_status': response.status,
                        'message': f'Health endpoint returned status {response.status}'
                    }
    except asyncio.TimeoutError:
        return {
            'status': 'unhealthy',
            'message': f'Health check timed out after {timeout} seconds'
        }
    except aiohttp.ClientError as e:
        return {
            'status': 'unhealthy',
            'message': f'Connection error: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'Unexpected error: {str(e)}'
        }


async def check_database_connection() -> Dict[str, Any]:
    """
    Check database connectivity (simplified check).
    
    Returns:
        Dict containing database check results
    """
    try:
        # Import here to avoid circular imports
        from database import get_db_manager
        
        db_manager = await get_db_manager()
        # Simple connection test
        await db_manager.ping()
        await db_manager.close()
        
        return {
            'status': 'healthy',
            'message': 'Database connection successful'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'Database connection failed: {str(e)}'
        }


async def check_bot_connectivity() -> Dict[str, Any]:
    """
    Check if bot token is valid and bot can connect to Telegram.
    
    Returns:
        Dict containing bot connectivity results
    """
    try:
        from aiogram import Bot
        from config import config
        
        if not config.BOT_TOKEN:
            return {
                'status': 'unhealthy',
                'message': 'Bot token not configured'
            }
        
        bot = Bot(token=config.BOT_TOKEN)
        try:
            me = await bot.get_me()
            await bot.session.close()
            
            return {
                'status': 'healthy',
                'message': f'Bot connected successfully (username: @{me.username})'
            }
        except Exception as e:
            await bot.session.close()
            return {
                'status': 'unhealthy',
                'message': f'Bot connection failed: {str(e)}'
            }
            
    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'Bot check error: {str(e)}'
        }


async def comprehensive_health_check() -> Dict[str, Any]:
    """
    Perform comprehensive health checks.
    
    Returns:
        Dict containing all health check results
    """
    port = os.getenv('PORT', '8000')
    base_url = f"http://localhost:{port}"
    health_url = f"{base_url}/health"
    
    logger.info("Starting comprehensive health check...")
    
    # Perform all checks concurrently
    health_endpoint_task = check_health_endpoint(health_url)
    database_task = check_database_connection()
    bot_task = check_bot_connectivity()
    
    health_endpoint_result, database_result, bot_result = await asyncio.gather(
        health_endpoint_task,
        database_task,
        bot_task,
        return_exceptions=True
    )
    
    # Handle exceptions from gather
    if isinstance(health_endpoint_result, Exception):
        health_endpoint_result = {
            'status': 'unhealthy',
            'message': f'Health endpoint check failed: {str(health_endpoint_result)}'
        }
    
    if isinstance(database_result, Exception):
        database_result = {
            'status': 'unhealthy',
            'message': f'Database check failed: {str(database_result)}'
        }
    
    if isinstance(bot_result, Exception):
        bot_result = {
            'status': 'unhealthy',
            'message': f'Bot check failed: {str(bot_result)}'
        }
    
    # Aggregate results
    results = {
        'overall_status': 'healthy',
        'timestamp': asyncio.get_event_loop().time(),
        'checks': {
            'health_endpoint': health_endpoint_result,
            'database': database_result,
            'bot': bot_result
        }
    }
    
    # Determine overall status
    unhealthy_checks = [
        name for name, result in results['checks'].items() 
        if result.get('status') != 'healthy'
    ]
    
    if unhealthy_checks:
        results['overall_status'] = 'unhealthy'
        results['failed_checks'] = unhealthy_checks
    
    return results


async def simple_health_check() -> bool:
    """
    Simple health check that returns True if the application is healthy.
    
    Returns:
        True if healthy, False otherwise
    """
    try:
        port = os.getenv('PORT', '8000')
        health_url = f"http://localhost:{port}/health"
        
        result = await check_health_endpoint(health_url, timeout=5)
        return result.get('status') == 'healthy'
        
    except Exception as e:
        logger.error(f"Simple health check failed: {e}")
        return False


async def main():
    """Main function for standalone health check execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Health check for Telegram Rewards Bot')
    parser.add_argument(
        '--mode', 
        choices=['simple', 'comprehensive'], 
        default='simple',
        help='Health check mode'
    )
    parser.add_argument(
        '--timeout', 
        type=int, 
        default=30,
        help='Overall timeout in seconds'
    )
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'comprehensive':
            logger.info("Running comprehensive health check...")
            result = await asyncio.wait_for(
                comprehensive_health_check(), 
                timeout=args.timeout
            )
            
            print(f"Health Check Results:")
            print(f"Overall Status: {result['overall_status']}")
            print("\nDetailed Results:")
            for check_name, check_result in result['checks'].items():
                status = check_result.get('status', 'unknown')
                message = check_result.get('message', 'No message')
                print(f"  {check_name}: {status} - {message}")
            
            if result['overall_status'] == 'healthy':
                sys.exit(0)
            else:
                sys.exit(1)
                
        else:  # simple mode
            logger.info("Running simple health check...")
            is_healthy = await asyncio.wait_for(
                simple_health_check(), 
                timeout=args.timeout
            )
            
            if is_healthy:
                print("Health check: PASSED")
                sys.exit(0)
            else:
                print("Health check: FAILED")
                sys.exit(1)
                
    except asyncio.TimeoutError:
        logger.error(f"Health check timed out after {args.timeout} seconds")
        print("Health check: TIMEOUT")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Health check error: {e}")
        print(f"Health check: ERROR - {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
