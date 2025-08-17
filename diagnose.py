#!/usr/bin/env python3
"""
Diagnosis script to help troubleshoot Railway deployment issues.
"""

import os
import sys
import asyncio
import aiohttp
from typing import List, Dict, Any

def check_environment_variables() -> Dict[str, Any]:
    """Check if required environment variables are set."""
    required_vars = [
        'BOT_TOKEN',
        'DATABASE_URL', 
        'TATUM_API_KEY',
        'TOKEN_CONTRACT_ADDRESS'
    ]
    
    optional_vars = [
        'PORT',
        'ENVIRONMENT',
        'ADMIN_USER_IDS',
        'BLOCKCHAIN_NETWORK'
    ]
    
    missing_required = []
    present_vars = {}
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_required.append(var)
        else:
            # Mask sensitive values
            if 'TOKEN' in var or 'KEY' in var:
                present_vars[var] = value[:10] + "***" if len(value) > 10 else "***"
            else:
                present_vars[var] = value
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            present_vars[var] = value
    
    return {
        'missing_required': missing_required,
        'present_vars': present_vars,
        'all_required_present': len(missing_required) == 0
    }

async def check_database_connection() -> Dict[str, Any]:
    """Check database connectivity."""
    try:
        # Import config to validate configuration
        from config import config
        config.validate()
        
        # Try to connect to database
        from database import get_db_manager
        db_manager = await get_db_manager()
        
        # Test ping
        await db_manager.ping()
        await db_manager.close()
        
        return {
            'status': 'success',
            'message': 'Database connection successful'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Database connection failed: {str(e)}'
        }

async def check_bot_token() -> Dict[str, Any]:
    """Check bot token validity."""
    try:
        from config import config
        
        if not config.BOT_TOKEN:
            return {
                'status': 'error',
                'message': 'Bot token not configured'
            }
        
        from aiogram import Bot
        bot = Bot(token=config.BOT_TOKEN)
        
        try:
            me = await bot.get_me()
            await bot.session.close()
            
            return {
                'status': 'success',
                'message': f'Bot token valid (username: @{me.username})'
            }
        except Exception as e:
            await bot.session.close()
            return {
                'status': 'error',
                'message': f'Bot token validation failed: {str(e)}'
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Bot token check error: {str(e)}'
        }

async def check_port_binding() -> Dict[str, Any]:
    """Check if the application can bind to the configured port."""
    try:
        from config import config
        port = config.PORT
        
        # Try to create a simple server to test port binding
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
            
            return {
                'status': 'success',
                'message': f'Port {port} is available for binding'
            }
        except OSError as e:
            sock.close()
            return {
                'status': 'error',
                'message': f'Cannot bind to port {port}: {str(e)}'
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Port check error: {str(e)}'
        }

def print_diagnosis_results(results: Dict[str, Any]):
    """Print diagnosis results in a formatted way."""
    print("=== RAILWAY DEPLOYMENT DIAGNOSIS ===\n")
    
    # Environment Variables
    print("1. ENVIRONMENT VARIABLES:")
    env_results = results['environment']
    if env_results['all_required_present']:
        print("   ✅ All required environment variables are present")
    else:
        print("   ❌ Missing required environment variables:")
        for var in env_results['missing_required']:
            print(f"      - {var}")
    
    print("\n   Present variables:")
    for var, value in env_results['present_vars'].items():
        print(f"      {var} = {value}")
    
    # Database
    print("\n2. DATABASE CONNECTION:")
    db_results = results['database']
    if db_results['status'] == 'success':
        print(f"   ✅ {db_results['message']}")
    else:
        print(f"   ❌ {db_results['message']}")
    
    # Bot Token
    print("\n3. BOT TOKEN:")
    bot_results = results['bot']
    if bot_results['status'] == 'success':
        print(f"   ✅ {bot_results['message']}")
    else:
        print(f"   ❌ {bot_results['message']}")
    
    # Port
    print("\n4. PORT BINDING:")
    port_results = results['port']
    if port_results['status'] == 'success':
        print(f"   ✅ {port_results['message']}")
    else:
        print(f"   ❌ {port_results['message']}")
    
    # Overall status
    print("\n=== OVERALL STATUS ===")
    all_success = all(
        results[key]['status'] == 'success' if isinstance(results[key], dict) and 'status' in results[key]
        else results[key]['all_required_present'] if key == 'environment'
        else True
        for key in results
    )
    
    if all_success:
        print("✅ All checks passed! The application should be ready for deployment.")
    else:
        print("❌ Some checks failed. Please fix the issues above before deploying.")
        
    print("\n=== TROUBLESHOOTING TIPS ===")
    print("- If health checks are failing on Railway:")
    print("  1. Check Railway logs for startup errors")
    print("  2. Ensure all environment variables are set in Railway")
    print("  3. Verify database URL is accessible from Railway")
    print("  4. Check if the application is listening on 0.0.0.0 (not localhost)")
    print("  5. Make sure the health check endpoint (/health) is responding")

async def main():
    """Main diagnosis function."""
    print("Starting diagnosis...\n")
    
    # Run all checks
    results = {
        'environment': check_environment_variables(),
        'database': await check_database_connection(),
        'bot': await check_bot_token(),
        'port': await check_port_binding()
    }
    
    # Print results
    print_diagnosis_results(results)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDiagnosis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nDiagnosis failed: {e}")
        sys.exit(1)
