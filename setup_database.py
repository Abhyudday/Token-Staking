"""Database setup script for initial deployment."""

import asyncio
import logging
from database import get_db_manager
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_database():
    """Initialize database and create tables."""
    try:
        # Validate configuration
        config.validate()
        logger.info("Configuration validated")
        
        # Initialize database
        db_manager = await get_db_manager()
        logger.info("Database connection established")
        
        # Initialize some basic settings
        await db_manager.set_setting(
            "bot_version", 
            "1.0.0", 
            "Current bot version"
        )
        
        await db_manager.set_setting(
            "setup_date", 
            str(asyncio.get_event_loop().time()), 
            "Date when bot was first set up"
        )
        
        logger.info("Database setup completed successfully!")
        
        # Close connections
        await db_manager.close()
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(setup_database())
