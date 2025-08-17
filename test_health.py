#!/usr/bin/env python3
"""Simple test script to verify the health check endpoint."""

import asyncio
import aiohttp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_health_endpoint():
    """Test the health check endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            # Test root endpoint
            async with session.get('http://localhost:8000/') as response:
                logger.info(f"Root endpoint status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Root response: {data}")
                else:
                    logger.error(f"Root endpoint failed: {response.status}")
            
            # Test health endpoint
            async with session.get('http://localhost:8000/health') as response:
                logger.info(f"Health endpoint status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Health response: {data}")
                else:
                    logger.error(f"Health endpoint failed: {response.status}")
                    text = await response.text()
                    logger.error(f"Response text: {text}")
                    
    except aiohttp.ClientConnectorError:
        logger.error("Could not connect to server. Make sure the server is running on port 8000.")
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_health_endpoint())
