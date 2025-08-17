"""Admin handlers for the bot."""

import logging
import random
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from typing import List, Dict, Any

from database import get_db_manager
from blockchain import BlockchainMonitor
from bot.keyboards import (
    get_admin_keyboard, get_confirmation_keyboard, get_holder_detail_keyboard,
    get_transaction_pagination_keyboard, get_winners_pagination_keyboard,
    get_back_keyboard, get_winner_announcement_keyboard
)
from bot.utils import (
    is_admin, format_wallet_address, format_number, format_holding_period,
    get_rank_emoji, truncate_text, format_currency
)
from config import config

logger = logging.getLogger(__name__)

router = Router()


def admin_required(func):
    """Decorator to check admin permissions."""
    async def wrapper(event, *args, **kwargs):
        user_id = None
        if hasattr(event, 'from_user'):
            user_id = event.from_user.id
        elif hasattr(event, 'message') and hasattr(event.message, 'from_user'):
            user_id = event.message.from_user.id
        
        if not user_id or not is_admin(user_id):
            if hasattr(event, 'answer'):
                await event.answer("❌ Access denied. Admin only.", show_alert=True)
            else:
                await event.answer("❌ Access denied. Admin only.")
            return
        
        return await func(event, *args, **kwargs)
    return wrapper


@router.message(Command("admin"))
@admin_required
async def admin_command(message: Message):
    """Handle /admin command."""
    try:
        await message.answer(
            "🔧 **Admin Panel**\n\n"
            "Welcome to the admin panel! Use the buttons below to manage the bot.",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in admin command: {e}")
        await message.answer("❌ Something went wrong. Please try again later.")


@router.callback_query(F.data == "admin_menu")
@admin_required
async def admin_menu(callback: CallbackQuery):
    """Handle admin menu callback."""
    try:
        await callback.message.edit_text(
            "🔧 **Admin Panel**\n\n"
            "Welcome to the admin panel! Use the buttons below to manage the bot.",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin menu: {e}")
        await callback.answer("❌ Something went wrong.")


@router.callback_query(F.data == "admin_holders")
@admin_required
async def admin_holders(callback: CallbackQuery):
    """Handle admin holders list."""
    try:
        db_manager = await get_db_manager()
        
        # Get all holders
        leaderboard_data = await db_manager.get_leaderboard(limit=100)
        
        if not leaderboard_data:
            await callback.message.edit_text(
                "👥 **All Holders**\n\nNo holders found yet!",
                reply_markup=get_back_keyboard("admin_menu"),
                parse_mode="Markdown"
            )
            await callback.answer()
            return
        
        # Format holders list
        holders_msg = "👥 **All Holders**\n\n"
        
        eligible_count = 0
        total_balance = 0
        
        for i, holder_data in enumerate(leaderboard_data[:20], 1):  # Show top 20
            wallet = format_wallet_address(holder_data["wallet_address"])
            balance = format_number(holder_data["current_balance"])
            days = format_holding_period(holder_data["holding_days"])
            
            status = "✅" if holder_data["is_eligible"] else "❌"
            if holder_data["is_eligible"]:
                eligible_count += 1
            
            total_balance += holder_data["current_balance"]
            
            holders_msg += f"**#{i}** {wallet}\n"
            holders_msg += f"    💰 {balance} • 📅 {days} {status}\n\n"
        
        holders_msg += f"📊 **Summary:**\n"
        holders_msg += f"• Total Holders: {len(leaderboard_data)}\n"
        holders_msg += f"• Eligible for Rewards: {eligible_count}\n"
        holders_msg += f"• Total Balance: {format_number(total_balance)} tokens"
        
        if len(leaderboard_data) > 20:
            holders_msg += f"\n\n📄 Showing top 20 of {len(leaderboard_data)} holders"
        
        await callback.message.edit_text(
            truncate_text(holders_msg),
            reply_markup=get_back_keyboard("admin_menu"),
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing admin holders: {e}")
        await callback.answer("❌ Error loading holders. Please try again.")


@router.callback_query(F.data == "admin_pick_winner")
@admin_required
async def admin_pick_winner(callback: CallbackQuery):
    """Handle pick winner for current month."""
    try:
        db_manager = await get_db_manager()
        
        # Get current month/year
        now = datetime.now(timezone.utc)
        current_month = now.month
        current_year = now.year
        
        # Check if winner already exists for this month
        existing_winner = await db_manager.get_winner(current_month, current_year)
        if existing_winner:
            await callback.message.edit_text(
                f"🏆 **Winner Already Selected**\n\n"
                f"A winner has already been selected for {existing_winner.period_display}:\n\n"
                f"🎉 **Winner:** {format_wallet_address(existing_winner.holder.wallet_address)}\n"
                f"📅 **Holding Days:** {existing_winner.holding_days_at_selection}\n"
                f"💰 **Balance:** {format_number(float(existing_winner.balance_at_selection))} tokens\n\n"
                f"Do you want to select a new winner for next month?",
                reply_markup=get_back_keyboard("admin_menu"),
                parse_mode="Markdown"
            )
            await callback.answer()
            return
        
        # Get eligible holders
        eligible_holders = await db_manager.get_eligible_holders()
        
        if not eligible_holders:
            await callback.message.edit_text(
                "❌ **No Eligible Holders**\n\n"
                f"There are no holders eligible for the {now.strftime('%B %Y')} reward.\n\n"
                "Holders must:\n"
                f"• Hold tokens for at least {config.MINIMUM_HOLD_DAYS} days\n"
                "• Have a current balance > 0\n"
                "• Not have sold any tokens",
                reply_markup=get_back_keyboard("admin_menu"),
                parse_mode="Markdown"
            )
            await callback.answer()
            return
        
        # Show confirmation with eligible holders count
        confirmation_msg = (
            f"🎲 **Select Winner for {now.strftime('%B %Y')}**\n\n"
            f"📊 **Eligible Holders:** {len(eligible_holders)}\n\n"
            "A random winner will be selected from all eligible holders.\n\n"
            "⚠️ **This action cannot be undone!**"
        )
        
        await callback.message.edit_text(
            confirmation_msg,
            reply_markup=get_confirmation_keyboard("pick_winner", f"{current_month}:{current_year}"),
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in pick winner: {e}")
        await callback.answer("❌ Error preparing winner selection. Please try again.")


@router.callback_query(F.data.startswith("confirm:pick_winner"))
@admin_required
async def confirm_pick_winner(callback: CallbackQuery):
    """Confirm and execute winner selection."""
    try:
        # Parse month and year from callback data
        data_parts = callback.data.split(":")
        current_month = int(data_parts[2])
        current_year = int(data_parts[3])
        
        db_manager = await get_db_manager()
        
        # Get eligible holders again
        eligible_holders = await db_manager.get_eligible_holders()
        
        if not eligible_holders:
            await callback.answer("❌ No eligible holders found!", show_alert=True)
            return
        
        # Randomly select winner
        winner_holder = random.choice(eligible_holders)
        
        # Create winner record
        winner = await db_manager.create_winner(
            holder_id=winner_holder.id,
            month=current_month,
            year=current_year,
            reward_amount="TBD - Admin to send manually"
        )
        
        # Format winner announcement
        announcement_msg = (
            f"🎉 **WINNER SELECTED!**\n\n"
            f"🏆 **Period:** {winner.period_display}\n"
            f"🎯 **Winner:** {format_wallet_address(winner_holder.wallet_address)}\n"
            f"📅 **Holding Days:** {winner.holding_days_at_selection}\n"
            f"💰 **Balance:** {format_number(float(winner.balance_at_selection))} tokens\n"
            f"👥 **Selected from:** {len(eligible_holders)} eligible holders\n\n"
            f"🔔 **Next Steps:**\n"
            f"1. Send reward to winner manually\n"
            f"2. Announce in the group\n"
            f"3. Mark reward as sent in admin panel"
        )
        
        await callback.message.edit_text(
            announcement_msg,
            reply_markup=get_winner_announcement_keyboard(winner.id),
            parse_mode="Markdown"
        )
        
        # Log the winner selection
        logger.info(f"Winner selected for {current_month}/{current_year}: {winner_holder.wallet_address}")
        
        await callback.answer("🎉 Winner selected successfully!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error confirming winner selection: {e}")
        await callback.answer("❌ Error selecting winner. Please try again.", show_alert=True)


@router.callback_query(F.data.startswith("admin_winners"))
@admin_required
async def admin_winners(callback: CallbackQuery):
    """Handle admin winners list."""
    try:
        # Parse page number
        page = 0
        if ":" in callback.data:
            page = int(callback.data.split(":")[1])
        
        db_manager = await get_db_manager()
        
        # Get recent winners
        per_page = 5
        all_winners = await db_manager.get_recent_winners(limit=50)
        
        # Paginate results
        offset = page * per_page
        page_winners = all_winners[offset:offset + per_page]
        total_pages = (len(all_winners) + per_page - 1) // per_page if all_winners else 1
        
        if not page_winners:
            await callback.message.edit_text(
                "🏆 **Recent Winners**\n\nNo winners yet!",
                reply_markup=get_back_keyboard("admin_menu"),
                parse_mode="Markdown"
            )
            await callback.answer()
            return
        
        # Format winners list
        winners_msg = "🏆 **Recent Winners**\n\n"
        
        for winner in page_winners:
            status = "✅ Sent" if winner.reward_sent else "⏳ Pending"
            
            winners_msg += f"📅 **{winner.period_display}**\n"
            winners_msg += f"🎯 Winner: {format_wallet_address(winner.holder.wallet_address)}\n"
            winners_msg += f"📊 Balance: {format_number(float(winner.balance_at_selection))} tokens\n"
            winners_msg += f"⏰ Days Held: {winner.holding_days_at_selection}\n"
            winners_msg += f"💰 Reward: {status}\n\n"
        
        winners_msg += f"📄 Page {page + 1} of {total_pages}"
        
        await callback.message.edit_text(
            truncate_text(winners_msg),
            reply_markup=get_winners_pagination_keyboard(page, total_pages),
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing admin winners: {e}")
        await callback.answer("❌ Error loading winners. Please try again.")


@router.callback_query(F.data == "admin_stats")
@admin_required
async def admin_stats(callback: CallbackQuery):
    """Handle admin statistics."""
    try:
        db_manager = await get_db_manager()
        
        # Get statistics
        leaderboard_data = await db_manager.get_leaderboard(limit=1000)
        recent_winners = await db_manager.get_recent_winners(limit=10)
        
        # Calculate stats
        total_holders = len(leaderboard_data)
        eligible_holders = sum(1 for h in leaderboard_data if h["is_eligible"])
        total_balance = sum(h["current_balance"] for h in leaderboard_data)
        avg_balance = total_balance / total_holders if total_holders > 0 else 0
        avg_holding_days = sum(h["holding_days"] for h in leaderboard_data) / total_holders if total_holders > 0 else 0
        
        # Top holder stats
        top_holder = leaderboard_data[0] if leaderboard_data else None
        
        stats_msg = "📊 **Bot Statistics**\n\n"
        
        stats_msg += "👥 **Holder Stats:**\n"
        stats_msg += f"• Total Holders: {total_holders}\n"
        stats_msg += f"• Eligible for Rewards: {eligible_holders}\n"
        stats_msg += f"• Eligibility Rate: {(eligible_holders/total_holders*100):.1f}%\n\n" if total_holders > 0 else ""
        
        stats_msg += "💰 **Token Stats:**\n"
        stats_msg += f"• Total Balance Tracked: {format_number(total_balance)}\n"
        stats_msg += f"• Average Balance: {format_number(avg_balance)}\n"
        stats_msg += f"• Average Holding Period: {format_holding_period(int(avg_holding_days))}\n\n"
        
        if top_holder:
            stats_msg += "🏆 **Top Holder:**\n"
            stats_msg += f"• Wallet: {format_wallet_address(top_holder['wallet_address'])}\n"
            stats_msg += f"• Balance: {format_number(top_holder['current_balance'])}\n"
            stats_msg += f"• Holding: {format_holding_period(top_holder['holding_days'])}\n\n"
        
        stats_msg += "🎲 **Reward Stats:**\n"
        stats_msg += f"• Total Winners: {len(recent_winners)}\n"
        
        if recent_winners:
            latest_winner = recent_winners[0]
            stats_msg += f"• Latest Winner: {latest_winner.period_display}\n"
        
        await callback.message.edit_text(
            truncate_text(stats_msg),
            reply_markup=get_back_keyboard("admin_menu"),
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing admin stats: {e}")
        await callback.answer("❌ Error loading statistics. Please try again.")


@router.callback_query(F.data == "admin_update_balances")
@admin_required
async def admin_update_balances(callback: CallbackQuery):
    """Handle update all balances."""
    try:
        await callback.message.edit_text(
            "🔄 **Updating All Balances**\n\n"
            "This will update token balances for all holders from the blockchain.\n\n"
            "⚠️ **This may take a few minutes!**",
            reply_markup=get_confirmation_keyboard("update_balances"),
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in update balances: {e}")
        await callback.answer("❌ Something went wrong.")


@router.callback_query(F.data.startswith("confirm:update_balances"))
@admin_required
async def confirm_update_balances(callback: CallbackQuery):
    """Confirm and execute balance update."""
    try:
        await callback.message.edit_text(
            "🔄 **Updating Balances...**\n\n"
            "Please wait while we update all holder balances from the blockchain.\n\n"
            "⏳ This may take a few minutes...",
            parse_mode="Markdown"
        )
        
        # Initialize blockchain monitor
        monitor = BlockchainMonitor()
        await monitor.initialize()
        
        # Update all balances
        await monitor.update_all_balances()
        
        await monitor.close()
        
        await callback.message.edit_text(
            "✅ **Balances Updated Successfully!**\n\n"
            "All holder balances have been updated from the blockchain.",
            reply_markup=get_back_keyboard("admin_menu"),
            parse_mode="Markdown"
        )
        
        await callback.answer("✅ Balances updated successfully!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error updating balances: {e}")
        await callback.message.edit_text(
            "❌ **Error Updating Balances**\n\n"
            "Something went wrong while updating balances. Please try again later.",
            reply_markup=get_back_keyboard("admin_menu"),
            parse_mode="Markdown"
        )
        await callback.answer("❌ Error updating balances.", show_alert=True)


@router.callback_query(F.data == "admin_settings")
@admin_required
async def admin_settings(callback: CallbackQuery):
    """Handle admin settings."""
    try:
        settings_msg = (
            "⚙️ **Bot Settings**\n\n"
            f"🔧 **Current Configuration:**\n"
            f"• Minimum Hold Days: {config.MINIMUM_HOLD_DAYS}\n"
            f"• Token Contract: `{format_wallet_address(config.TOKEN_CONTRACT_ADDRESS)}`\n"
            f"• Blockchain Network: {config.BLOCKCHAIN_NETWORK}\n"
            f"• Admin Users: {len(config.ADMIN_USER_IDS)}\n\n"
            f"💡 To change settings, update environment variables and restart the bot."
        )
        
        await callback.message.edit_text(
            settings_msg,
            reply_markup=get_back_keyboard("admin_menu"),
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing admin settings: {e}")
        await callback.answer("❌ Error loading settings. Please try again.")


# Error handler for admin router
@router.error()
async def admin_error_handler(event, exception):
    """Handle errors in admin handlers."""
    logger.error(f"Error in admin handlers: {exception}")
    
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
