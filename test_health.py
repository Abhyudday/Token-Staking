#!/usr/bin/env python3
"""
Quick test script to verify health check functionality locally.
"""

import asyncio
import aiohttp
import sys
import os

async def test_health_check():
    """Test the health check endpoint locally."""
    port = os.getenv('PORT', '8000')
    health_url = f"http://localhost:{port}/health"
    
    print(f"Testing health check at: {health_url}")
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(health_url) as response:
                print(f"Status Code: {response.status}")
                
                if response.content_type == 'application/json':
                    data = await response.json()
                    print("Response JSON:")
                    import json
                    print(json.dumps(data, indent=2))
                else:
                    text = await response.text()
                    print(f"Response Text: {text}")
                
                return response.status == 200
                
    except aiohttp.ClientConnectorError:
        print("ERROR: Could not connect to the application. Is it running?")
        return False
    except asyncio.TimeoutError:
        print("ERROR: Health check request timed out")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def main():
    """Main function."""
    print("=== Health Check Test ===")
    
    success = await test_health_check()
    
    if success:
        print("\n✅ Health check PASSED")
        sys.exit(0)
    else:
        print("\n❌ Health check FAILED")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
