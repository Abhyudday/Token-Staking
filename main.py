#!/usr/bin/env python3
"""
Token Holder Bot - Main Entry Point

This bot takes daily snapshots of Solana token holders and maintains a leaderboard
based on how long each wallet has held tokens.

Features:
- Daily automated snapshots via SOLSCAN Pro API
- PostgreSQL database storage (Railway)
- Leaderboard ranking by days held
- Admin panel for configuration
- Minimum USD threshold filtering
- Health check endpoints for Railway monitoring
"""

import asyncio
import logging
import signal
import sys
import threading
import os
from telegram_bot import TokenHolderBot
from scheduler import SnapshotScheduler
from config import Config
from healthcheck_server import run_health_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class TokenHolderBotApp:
    def __init__(self):
        self.bot = None
        self.scheduler = None
        self.health_server_thread = None
        self.running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
    
    def _start_health_server(self):
        """Start health check server in a separate thread"""
        try:
            # Get port from environment or use default
            port = int(os.getenv('PORT', 8000))
            logger.info(f"Starting health check server on port {port}")
            
            # Run health server in thread
            self.health_server_thread = threading.Thread(
                target=run_health_server, 
                args=(port,),
                daemon=True
            )
            self.health_server_thread.start()
            
            logger.info("Health check server started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start health server: {e}")
    
    async def start(self):
        """Start the bot and scheduler"""
        try:
            logger.info("Starting Token Holder Bot Application...")
            
            # Validate configuration
            Config.validate()
            logger.info("Configuration validated successfully")
            
            # Start health check server
            self._start_health_server()
            
            # Initialize bot
            self.bot = TokenHolderBot()
            logger.info("Bot initialized successfully")
            
            # Initialize scheduler
            self.scheduler = SnapshotScheduler()
            logger.info("Scheduler initialized successfully")
            
            # Start scheduler
            self.scheduler.start_scheduler()
            logger.info("Scheduler started successfully")
            
            self.running = True
            logger.info("Application started successfully")
            logger.info("Health check endpoints available at /health and /")
            
            # Start the bot (this will block)
            self.bot.run()
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            self.shutdown()
            sys.exit(1)
    
    def shutdown(self):
        """Shutdown the application gracefully"""
        if not self.running:
            return
        
        logger.info("Shutting down application...")
        self.running = False
        
        try:
            # Stop scheduler
            if self.scheduler:
                self.scheduler.close()
                logger.info("Scheduler stopped")
            
            # Stop bot
            if self.bot:
                self.bot.stop()
                logger.info("Bot stopped")
                
            # Health server will stop automatically as it's a daemon thread
            logger.info("Health check server stopped")
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("Application shutdown complete")

async def main():
    """Main entry point"""
    app = TokenHolderBotApp()
    
    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
