"""User handlers for the bot."""

import logging
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import Text
from typing import Optional

from database import get_db_manager
from blockchain import BlockchainMonitor
from bot.keyboards import (
    get_main_keyboard, get_leaderboard_keyboard, get_wallet_link_keyboard,
    get_back_keyboard, get_refresh_keyboard
)
from bot.utils import (
    format_wallet_address, format_number, format_holding_period, get_rank_emoji,
    get_welcome_message, get_help_message, get_status_message,
    validate_wallet_address_format, truncate_text
)
from config import config

logger = logging.getLogger(__name__)

# For aiogram 2.x, we'll use the dispatcher directly instead of Router
# The handlers will be registered in the main bot setup

class WalletLinkStates(StatesGroup):
    waiting_for_wallet = State()


async def start_command(message: types.Message):
    """Handle /start command."""
    try:
        welcome_msg = get_welcome_message()
        await message.answer(
            welcome_msg,
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer("❌ Something went wrong. Please try again later.")


async def help_command(message: types.Message):
    """Handle /help command."""
    try:
        help_msg = get_help_message()
        await message.answer(
            help_msg,
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await message.answer("❌ Something went wrong. Please try again later.")


async def back_to_main(callback_query: types.CallbackQuery):
    """Handle back to main menu."""
    try:
        welcome_msg = get_welcome_message()
        await callback_query.message.edit_text(
            welcome_msg,
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in back to main: {e}")
        await callback_query.answer("❌ Something went wrong.")


async def help_callback(callback_query: types.CallbackQuery):
    """Handle help button callback."""
    try:
        help_msg = get_help_message()
        await callback_query.message.edit_text(
            help_msg,
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in help callback: {e}")
        await callback_query.answer("❌ Something went wrong.")


async def check_status(callback_query: types.CallbackQuery):
    """Handle check status callback."""
    try:
        db_manager = await get_db_manager()
        holder = await db_manager.get_holder_by_telegram_id(callback_query.from_user.id)
        
        if not holder:
            await callback_query.message.edit_text(
                "❌ **Wallet Not Linked**\n\nPlease link your wallet address first to check your status!",
                reply_markup=get_wallet_link_keyboard(),
                parse_mode="Markdown"
            )
            await callback_query.answer()
            return
        
        # Get detailed status from blockchain monitor
        monitor = BlockchainMonitor()
        await monitor.initialize()
        
        status_data = await monitor.check_holder_eligibility(holder.wallet_address)
        status_msg = get_status_message(status_data)
        
        await monitor.close()
        
        await callback_query.message.edit_text(
            status_msg,
            reply_markup=get_refresh_keyboard("check_status"),
            parse_mode="Markdown"
        )
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        await callback_query.answer("❌ Error checking status. Please try again.")


async def leaderboard(callback_query: types.CallbackQuery):
    """Handle leaderboard callback."""
    try:
        # Parse page number from callback data
        page = 0
        if ":" in callback_query.data:
            page = int(callback_query.data.split(":")[1])
        
        db_manager = await get_db_manager()
        
        # Get leaderboard data
        per_page = 10
        offset = page * per_page
        
        leaderboard_data = await db_manager.get_leaderboard(limit=per_page + offset)
        
        # Paginate results
        page_data = leaderboard_data[offset:offset + per_page]
        total_pages = (len(leaderboard_data) + per_page - 1) // per_page
        
        if not page_data:
            await callback_query.message.edit_text(
                "📊 **Leaderboard**\n\nNo holders found yet!",
                reply_markup=get_back_keyboard(),
                parse_mode="Markdown"
            )
            await callback_query.answer()
            return
        
        # Format leaderboard message
        leaderboard_msg = "🏆 **Token Holder Leaderboard**\n\n"
        
        for i, holder_data in enumerate(page_data, start=offset + 1):
            rank_emoji = get_rank_emoji(i)
            wallet = format_wallet_address(holder_data["wallet_address"])
            balance = format_number(holder_data["current_balance"])
            days = format_holding_period(holder_data["holding_days"])
            
            status = "✅" if holder_data["is_eligible"] else "⏳"
            
            leaderboard_msg += f"{rank_emoji} **#{i}** {wallet}\n"
            leaderboard_msg += f"    💰 {balance} tokens • 📅 {days} {status}\n\n"
        
        leaderboard_msg += f"📄 Page {page + 1} of {total_pages}"
        
        await callback_query.message.edit_text(
            truncate_text(leaderboard_msg),
            reply_markup=get_leaderboard_keyboard(page, total_pages),
            parse_mode="Markdown"
        )
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error showing leaderboard: {e}")
        await callback_query.answer("❌ Error loading leaderboard. Please try again.")


async def my_rank(callback_query: types.CallbackQuery):
    """Handle my rank callback."""
    try:
        db_manager = await get_db_manager()
        holder = await db_manager.get_holder_by_telegram_id(callback_query.from_user.id)
        
        if not holder:
            await callback_query.answer("❌ Please link your wallet first!", show_alert=True)
            return
        
        rank = await db_manager.get_holder_rank(holder.id)
        
        if rank:
            rank_emoji = get_rank_emoji(rank)
            msg = f"{rank_emoji} You are ranked **#{rank}** on the leaderboard!"
        else:
            msg = "❌ Unable to determine your rank. Make sure you have tokens!"
        
        await callback_query.answer(msg, show_alert=True)
        
    except Exception as e:
        logger.error(f"Error getting user rank: {e}")
        await callback_query.answer("❌ Error getting rank. Please try again.", show_alert=True)


async def link_wallet(callback_query: types.CallbackQuery, state: FSMContext):
    """Handle link wallet callback."""
    try:
        await callback_query.message.edit_text(
            "🔗 **Link Your Wallet**\n\n"
            "Please send your wallet address to start tracking your token holdings.\n\n"
            "📝 **Example:** `0x1234567890abcdef...`\n\n"
            "⚠️ Make sure to send the correct address!",
            reply_markup=get_wallet_link_keyboard(),
            parse_mode="Markdown"
        )
        
        await state.set_state(WalletLinkStates.waiting_for_wallet)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in link wallet: {e}")
        await callback_query.answer("❌ Something went wrong.")


async def process_wallet_address(message: types.Message, state: FSMContext):
    """Process wallet address input."""
    try:
        wallet_address = message.text.strip()
        
        # Validate wallet address format
        if not validate_wallet_address_format(wallet_address):
            await message.answer(
                "❌ **Invalid Wallet Address**\n\n"
                "Please send a valid wallet address starting with `0x` and 42 characters long.\n\n"
                "📝 **Example:** `0x1234567890abcdef...`",
                parse_mode="Markdown"
            )
            return
        
        # Initialize blockchain monitor
        monitor = BlockchainMonitor()
        await monitor.initialize()
        
        # Validate address with blockchain
        is_valid = await monitor.tatum.validate_wallet_address(wallet_address)
        if not is_valid:
            await message.answer(
                "❌ **Invalid Wallet Address**\n\n"
                "The wallet address format is incorrect. Please check and try again.",
                parse_mode="Markdown"
            )
            await monitor.close()
            return
        
        # Check if address already linked to another user
        db_manager = await get_db_manager()
        existing_holder = await db_manager.get_holder_by_wallet(wallet_address)
        
        if existing_holder and existing_holder.telegram_user_id and existing_holder.telegram_user_id != message.from_user.id:
            await message.answer(
                "❌ **Wallet Already Linked**\n\n"
                "This wallet address is already linked to another user.",
                parse_mode="Markdown"
            )
            await monitor.close()
            return
        
        # Get current balance
        current_balance = await monitor.tatum.get_token_balance(wallet_address)
        
        # Create or update holder record
        holder = await db_manager.create_or_update_holder(
            wallet_address=wallet_address,
            telegram_user_id=message.from_user.id,
            telegram_username=message.from_user.username,
            current_balance=current_balance or 0.0
        )
        
        # Sync transaction history if it's a new holder
        if not existing_holder:
            await monitor.sync_wallet_transactions(wallet_address)
        
        await monitor.close()
        
        # Clear state
        await state.clear()
        
        # Show success message with status
        if current_balance and current_balance > 0:
            status_data = await monitor.check_holder_eligibility(wallet_address)
            status_msg = get_status_message(status_data)
            
            success_msg = f"✅ **Wallet Linked Successfully!**\n\n{status_msg}"
        else:
            success_msg = (
                "✅ **Wallet Linked Successfully!**\n\n"
                f"📝 **Address:** `{format_wallet_address(wallet_address)}`\n\n"
                "💡 Once you purchase tokens, your holding period will start automatically!"
            )
        
        await message.answer(
            success_msg,
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error processing wallet address: {e}")
        await message.answer(
            "❌ **Error Linking Wallet**\n\n"
            "Something went wrong while linking your wallet. Please try again later.",
            parse_mode="Markdown"
        )
        await state.clear()


async def leaderboard_info(callback_query: types.CallbackQuery):
    """Handle leaderboard info callback."""
    await callback_query.answer(
        "📊 Leaderboard shows top token holders ranked by balance. "
        "✅ = Eligible for rewards, ⏳ = Still building eligibility",
        show_alert=True
    )


async def transaction_info(callback_query: types.CallbackQuery):
    """Handle transaction info callback."""
    await callback_query.answer(
        "📈 Transaction history shows all buy/sell activities for this wallet.",
        show_alert=True
    )


async def winners_info(callback_query: types.CallbackQuery):
    """Handle winners info callback."""
    await callback_query.answer(
        "🏆 Recent winners of monthly rewards. Winners are selected randomly from eligible holders.",
        show_alert=True
    )


async def unknown_message(message: types.Message):
    """Handle unknown messages."""
    try:
        await message.answer(
            "🤖 I didn't understand that command.\n\n"
            "Use the buttons below or type /help for available commands.",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in unknown message handler: {e}")


# Error handler for this router
async def error_handler(event, exception):
    """Handle errors in user handlers."""
    logger.error(f"Error in user handlers: {exception}")
    
    if hasattr(event, 'update') and hasattr(event.update, 'callback_query'):
        try:
            await event.update.callback_query.answer("❌ Something went wrong. Please try again.")
        except:
            pass
    elif hasattr(event, 'update') and hasattr(event.update, 'message'):
        try:
            await event.update.message.answer("❌ Something went wrong. Please try again.")
        except:
            pass
