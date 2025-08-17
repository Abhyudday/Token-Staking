"""Utility functions for the bot."""

from typing import Optional
from config import config


def format_wallet_address(address: str, show_chars: int = 6) -> str:
    """Format wallet address for display."""
    if not address or len(address) < show_chars * 2:
        return address
    return f"{address[:show_chars]}...{address[-show_chars:]}"


def format_number(number: float, decimals: int = 2) -> str:
    """Format number for display."""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.{decimals}f}M"
    elif number >= 1_000:
        return f"{number / 1_000:.{decimals}f}K"
    else:
        return f"{number:.{decimals}f}"


def format_currency(amount: float) -> str:
    """Format currency amount."""
    return f"${format_number(amount, 2)}"


def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in config.ADMIN_USER_IDS


def format_holding_period(days: int) -> str:
    """Format holding period for display."""
    if days >= 365:
        years = days // 365
        remaining_days = days % 365
        if remaining_days > 0:
            return f"{years}y {remaining_days}d"
        return f"{years}y"
    elif days >= 30:
        months = days // 30
        remaining_days = days % 30
        if remaining_days > 0:
            return f"{months}mo {remaining_days}d"
        return f"{months}mo"
    else:
        return f"{days}d"


def get_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Create a progress bar."""
    if total == 0:
        return "▱" * length
    
    filled = int((current / total) * length)
    bar = "▰" * filled + "▱" * (length - filled)
    return bar


def get_rank_emoji(rank: int) -> str:
    """Get emoji for leaderboard rank."""
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    elif rank <= 10:
        return "🏅"
    else:
        return "📊"


def truncate_text(text: str, max_length: int = 4096) -> str:
    """Truncate text to fit Telegram message limits."""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def validate_wallet_address_format(address: str) -> bool:
    """Basic validation for wallet address format."""
    if not address:
        return False
    
    # Remove whitespace
    address = address.strip()
    
    # Check if it looks like an Ethereum address
    if address.startswith("0x") and len(address) == 42:
        try:
            # Check if the rest are valid hex characters
            int(address[2:], 16)
            return True
        except ValueError:
            return False
    
    return False


def get_welcome_message() -> str:
    """Get welcome message for new users."""
    return """
🎉 **Welcome to the Token Holder Rewards Bot!**

This bot rewards loyal token holders who diamond hand for at least 30 days! 💎🙌

**What you can do:**
• Check your holding status and eligibility
• View the community leaderboard
• Track your progress toward rewards
• Get notified about monthly winners

**How it works:**
1. Hold tokens for 30+ days without selling
2. Get automatically entered into monthly draws
3. Winners are announced and rewarded!

Use the buttons below to get started! 👇
    """.strip()


def get_help_message() -> str:
    """Get help message."""
    return """
**🔹 Commands & Features:**

**📊 Check Status** - View your holding status and days until eligibility

**🏆 Leaderboard** - See top holders and your rank

**📈 Link Wallet** - Connect your wallet address to track holdings

**ℹ️ Help** - Show this help message

**💡 Tips:**
• Hold tokens for 30+ days to be eligible for monthly rewards
• Don't sell or you'll lose eligibility
• Winners are selected randomly from eligible holders
• Check leaderboard to see your rank

Need more help? Contact our admins! 👨‍💼
    """.strip()


def get_status_message(status_data: dict) -> str:
    """Format status message for user."""
    if not status_data["eligible"]:
        if status_data["days_held"] == 0:
            return f"""
❌ **Wallet Not Found**

{status_data["reason"]}

Please link your wallet using the button below to start tracking your holdings! 👇
            """.strip()
        else:
            progress = min(status_data["days_held"] / config.MINIMUM_HOLD_DAYS, 1.0)
            progress_bar = get_progress_bar(status_data["days_held"], config.MINIMUM_HOLD_DAYS)
            
            return f"""
⏳ **Holding Progress**

📅 Days Held: **{status_data["days_held"]}** / {config.MINIMUM_HOLD_DAYS}
⏰ Days Remaining: **{status_data["days_remaining"]}**

{progress_bar} {progress:.0%}

💰 Current Balance: **{format_number(status_data.get("current_balance", 0))} tokens**

{status_data["reason"]}

Keep holding to become eligible for monthly rewards! 💎🙌
            """.strip()
    else:
        return f"""
✅ **Eligible for Rewards!**

🎉 Congratulations! You're eligible for monthly rewards!

📅 Days Held: **{status_data["days_held"]}** days
💰 Current Balance: **{format_number(status_data.get("current_balance", 0))} tokens**

You're automatically entered in the next monthly draw! 🎲

Good luck and keep holding! 💎🙌
        """.strip()
