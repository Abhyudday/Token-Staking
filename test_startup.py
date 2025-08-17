#!/usr/bin/env python3
"""
Simple startup test script to debug application initialization issues.
"""

import asyncio
import logging
import sys
import traceback

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_startup():
    """Test each startup step individually."""
    
    print("=== Testing Application Startup ===\n")
    
    # Test 1: Basic imports
    print("1. Testing imports...")
    try:
        import config
        print("   ✓ Config imported successfully")
    except Exception as e:
        print(f"   ✗ Config import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        from bot import create_bot, create_dispatcher
        print("   ✓ Bot module imported successfully")
    except Exception as e:
        print(f"   ✗ Bot module import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        from database import get_db_manager
        print("   ✓ Database module imported successfully")
    except Exception as e:
        print(f"   ✗ Database module import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        from blockchain import BlockchainMonitor
        print("   ✓ Blockchain module imported successfully")
    except Exception as e:
        print(f"   ✗ Blockchain module import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        from healthcheck import health_checker, quick_health_check
        print("   ✓ Healthcheck module imported successfully")
    except Exception as e:
        print(f"   ✗ Healthcheck module import failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 2: Configuration validation
    print("\n2. Testing configuration...")
    try:
        config.config.validate()
        print("   ✓ Configuration validation passed")
    except Exception as e:
        print(f"   ⚠ Configuration validation failed: {e}")
        print("   (This is expected without proper environment variables)")
    
    # Test 3: Health check
    print("\n3. Testing health check...")
    try:
        result = await quick_health_check()
        print(f"   ✓ Health check result: {result['status']}")
    except Exception as e:
        print(f"   ✗ Health check failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 4: Web server creation
    print("\n4. Testing web server creation...")
    try:
        from aiohttp import web
        from main import create_app
        
        app = await create_app()
        print("   ✓ Web application created successfully")
        
        # Test adding routes
        app.router.add_get('/test', lambda r: web.Response(text='test'))
        print("   ✓ Routes can be added")
        
    except Exception as e:
        print(f"   ✗ Web server creation failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 5: Minimal server startup
    print("\n5. Testing minimal server startup...")
    try:
        runner = web.AppRunner(app)
        await runner.setup()
        print("   ✓ AppRunner setup successful")
        
        site = web.TCPSite(runner, '127.0.0.1', 0)  # Use port 0 for testing
        await site.start()
        print("   ✓ Server started successfully")
        
        # Get the actual port
        port = site.name.port if hasattr(site.name, 'port') else 'unknown'
        print(f"   ✓ Server listening on port {port}")
        
        # Cleanup
        await runner.cleanup()
        print("   ✓ Server cleanup successful")
        
    except Exception as e:
        print(f"   ✗ Server startup failed: {e}")
        traceback.print_exc()
        return False
    
    print("\n=== All Tests Passed! ===")
    return True

async def test_main_startup():
    """Test the main startup function."""
    print("\n=== Testing Main Startup Function ===\n")
    
    try:
        import main
        print("✓ Main module imported successfully")
        
        # Test if we can create the lifespan context
        print("Testing lifespan context creation...")
        async with main.lifespan_context() as context:
            print("✓ Lifespan context created successfully")
            print(f"  Bot: {'✓' if context.get('bot') else '✗'}")
            print(f"  Database: {'✓' if context.get('db_manager') else '✗'}")
            print(f"  Blockchain: {'✓' if context.get('blockchain_monitor') else '✗'}")
        
        print("✓ Lifespan context test completed")
        return True
        
    except Exception as e:
        print(f"✗ Main startup test failed: {e}")
        traceback.print_exc()
        return False

async def main():
    """Run all startup tests."""
    try:
        # Test basic startup
        if not await test_startup():
            print("\n❌ Basic startup tests failed!")
            return False
        
        # Test main startup
        if not await test_main_startup():
            print("\n❌ Main startup tests failed!")
            return False
        
        print("\n🎉 All startup tests passed! Application should start successfully.")
        return True
        
    except Exception as e:
        print(f"\n💥 Unexpected error during testing: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
