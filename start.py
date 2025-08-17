#!/usr/bin/env python3
"""
Simple startup script for Railway deployment.
This script ensures the application starts properly in the Railway environment.
"""

import os
import sys
import time
import logging

# Configure basic logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Start the application with proper error handling."""
    try:
        logger.info("=== Railway Startup Script ===")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Python executable: {sys.executable}")
        logger.info(f"Python version: {sys.version}")
        logger.info("Environment variables:")
        for key, value in os.environ.items():
            if key in ['ENVIRONMENT', 'PORT', 'RAILWAY_PUBLIC_DOMAIN', 'RAILWAY_STATIC_URL']:
                logger.info(f"  {key}: {value}")
        
        # Log all environment variables for debugging (filter sensitive ones)
        logger.info("All environment variables (filtered):")
        for key, value in os.environ.items():
            if not any(sensitive in key.lower() for sensitive in ['token', 'key', 'password', 'secret']):
                logger.info(f"  {key}: {value}")
        
        # Wait a moment for Railway environment to be ready
        logger.info("Waiting 2 seconds for Railway environment...")
        time.sleep(2)
        
        # Import and run the main application
        logger.info("Importing main application...")
        from main import main as app_main
        
        logger.info("Starting main application...")
        import asyncio
        asyncio.run(app_main())
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("This usually means there's a missing dependency")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Startup error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
