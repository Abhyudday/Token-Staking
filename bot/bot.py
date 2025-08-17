"""Main bot setup and configuration."""

import logging
from aiogram import Bot, Dispatcher
from aiogram.types import ParseMode

from bot.handlers import user_handlers, admin_handlers
from config import config

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    """Create and configure the bot instance."""
    return Bot(
        token=config.BOT_TOKEN,
        parse_mode=ParseMode.MARKDOWN
    )


def setup_handlers(dp: Dispatcher) -> None:
    """Setup all bot handlers."""
    # Register command handlers
    dp.register_message_handler(user_handlers.start_command, commands=['start'])
    dp.register_message_handler(user_handlers.help_command, commands=['help'])
    
    # Register callback query handlers
    dp.register_callback_query_handler(user_handlers.back_to_main, lambda c: c.data == "back_to_main")
    dp.register_callback_query_handler(user_handlers.help_callback, lambda c: c.data == "help")
    dp.register_callback_query_handler(user_handlers.check_status, lambda c: c.data == "check_status")
    dp.register_callback_query_handler(user_handlers.leaderboard, lambda c: c.data.startswith("leaderboard"))
    dp.register_callback_query_handler(user_handlers.my_rank, lambda c: c.data == "my_rank")
    dp.register_callback_query_handler(user_handlers.link_wallet, lambda c: c.data == "link_wallet")
    dp.register_callback_query_handler(user_handlers.leaderboard_info, lambda c: c.data == "leaderboard_info")
    dp.register_callback_query_handler(user_handlers.transaction_info, lambda c: c.data == "transaction_info")
    dp.register_callback_query_handler(user_handlers.winners_info, lambda c: c.data == "winners_info")
    
    # Register state handlers
    dp.register_message_handler(
        user_handlers.process_wallet_address, 
        state=user_handlers.WalletLinkStates.waiting_for_wallet
    )
    
    # Register unknown message handler
    dp.register_message_handler(user_handlers.unknown_message)
    
    # Register error handler
    dp.register_errors_handler(user_handlers.error_handler)
    
    logger.info("Bot handlers setup completed")


async def create_dispatcher() -> Dispatcher:
    """Create and configure the dispatcher."""
    # Create dispatcher (no storage needed for v2)
    dp = Dispatcher()
    
    # Setup handlers
    setup_handlers(dp)
    
    return dp
