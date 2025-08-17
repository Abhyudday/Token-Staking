"""Keyboard layouts for the bot."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Get main menu keyboard for users."""
    builder = InlineKeyboardBuilder()
    
    # First row
    builder.row(
        InlineKeyboardButton(text="📊 Check Status", callback_data="check_status"),
        InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard")
    )
    
    # Second row
    builder.row(
        InlineKeyboardButton(text="📈 Link Wallet", callback_data="link_wallet"),
        InlineKeyboardButton(text="ℹ️ Help", callback_data="help")
    )
    
    return builder.as_markup()


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Get admin menu keyboard."""
    builder = InlineKeyboardBuilder()
    
    # First row
    builder.row(
        InlineKeyboardButton(text="👥 All Holders", callback_data="admin_holders"),
        InlineKeyboardButton(text="🎲 Pick Winner", callback_data="admin_pick_winner")
    )
    
    # Second row
    builder.row(
        InlineKeyboardButton(text="🏆 Recent Winners", callback_data="admin_winners"),
        InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats")
    )
    
    # Third row
    builder.row(
        InlineKeyboardButton(text="🔄 Update Balances", callback_data="admin_update_balances"),
        InlineKeyboardButton(text="⚙️ Settings", callback_data="admin_settings")
    )
    
    # Back button
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Main", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_leaderboard_keyboard(page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Get leaderboard navigation keyboard."""
    builder = InlineKeyboardBuilder()
    
    # Navigation buttons
    buttons = []
    
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"leaderboard:{page-1}"))
    
    # Page info
    buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="leaderboard_info"))
    
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"leaderboard:{page+1}"))
    
    if buttons:
        builder.row(*buttons)
    
    # Action buttons
    builder.row(
        InlineKeyboardButton(text="📊 My Rank", callback_data="my_rank"),
        InlineKeyboardButton(text="🔄 Refresh", callback_data="leaderboard:0")
    )
    
    # Back button
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Main", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_wallet_link_keyboard() -> InlineKeyboardMarkup:
    """Get wallet linking keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔙 Cancel", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_confirmation_keyboard(action: str, data: str = "") -> InlineKeyboardMarkup:
    """Get confirmation keyboard for admin actions."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm:{action}:{data}"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="admin_menu")
    )
    
    return builder.as_markup()


def get_winner_announcement_keyboard(winner_id: int) -> InlineKeyboardMarkup:
    """Get keyboard for winner announcement."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🎉 Congratulations!", callback_data=f"winner_congrats:{winner_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="🏆 View Leaderboard", callback_data="leaderboard"),
        InlineKeyboardButton(text="📊 Check My Status", callback_data="check_status")
    )
    
    return builder.as_markup()


def get_holder_detail_keyboard(holder_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Get keyboard for holder details view."""
    builder = InlineKeyboardBuilder()
    
    # Actions
    builder.row(
        InlineKeyboardButton(text="📊 View Transactions", callback_data=f"holder_transactions:{holder_id}:{page}"),
        InlineKeyboardButton(text="🔄 Update Balance", callback_data=f"update_holder:{holder_id}")
    )
    
    # Status actions
    builder.row(
        InlineKeyboardButton(text="❌ Mark Ineligible", callback_data=f"mark_ineligible:{holder_id}"),
        InlineKeyboardButton(text="✅ Mark Eligible", callback_data=f"mark_eligible:{holder_id}")
    )
    
    # Navigation
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Holders", callback_data="admin_holders")
    )
    
    return builder.as_markup()


def get_transaction_pagination_keyboard(holder_id: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Get pagination keyboard for transaction history."""
    builder = InlineKeyboardBuilder()
    
    # Navigation buttons
    buttons = []
    
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"holder_transactions:{holder_id}:{page-1}"))
    
    # Page info
    buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="transaction_info"))
    
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"holder_transactions:{holder_id}:{page+1}"))
    
    if buttons:
        builder.row(*buttons)
    
    # Back button
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Holder", callback_data=f"holder_detail:{holder_id}")
    )
    
    return builder.as_markup()


def get_winners_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Get pagination keyboard for winners list."""
    builder = InlineKeyboardBuilder()
    
    # Navigation buttons
    buttons = []
    
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"admin_winners:{page-1}"))
    
    # Page info
    buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="winners_info"))
    
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"admin_winners:{page+1}"))
    
    if buttons:
        builder.row(*buttons)
    
    # Actions
    builder.row(
        InlineKeyboardButton(text="🎲 Pick New Winner", callback_data="admin_pick_winner"),
        InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_winners:0")
    )
    
    # Back button
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_menu")
    )
    
    return builder.as_markup()


def get_back_keyboard(callback_data: str = "back_to_main") -> InlineKeyboardMarkup:
    """Get simple back button keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔙 Back", callback_data=callback_data)
    )
    
    return builder.as_markup()


def get_refresh_keyboard(action: str, data: str = "") -> InlineKeyboardMarkup:
    """Get refresh button keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔄 Refresh", callback_data=f"{action}:{data}" if data else action),
        InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")
    )
    
    return builder.as_markup()
