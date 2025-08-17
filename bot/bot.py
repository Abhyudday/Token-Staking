"""Main bot setup and configuration."""

import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import user_handlers, admin_handlers
from config import config

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    """Create and configure the bot instance."""
    return Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.MARKDOWN
        )
    )


def setup_handlers(dp: Dispatcher) -> None:
    """Setup all bot handlers."""
    # Include user handlers
    dp.include_router(user_handlers.router)
    
    # Include admin handlers
    dp.include_router(admin_handlers.router)
    
    logger.info("Bot handlers setup completed")


async def create_dispatcher() -> Dispatcher:
    """Create and configure the dispatcher."""
    # Use memory storage for FSM
    storage = MemoryStorage()
    
    # Create dispatcher
    dp = Dispatcher(storage=storage)
    
    # Setup handlers
    setup_handlers(dp)
    
    return dp
