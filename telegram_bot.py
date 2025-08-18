import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from database import Database
from snapshot_service import SnapshotService
from solscan_api import SolscanAPI
from config import Config
import json

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TokenHolderBot:
    def __init__(self):
        self.db = Database()
        self.snapshot_service = SnapshotService()
        self.solscan = SolscanAPI()
        self.token_address = Config.TOKEN_CONTRACT_ADDRESS
        
        # Initialize bot application
        self.application = Application.builder().token(Config.BOT_TOKEN).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup bot command handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        self.application.add_handler(CommandHandler("rank", self.rank_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("snapshot", self.snapshot_command))
        
        # Callback query handler for admin panel
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🚀 **Welcome to the Token Holder Bot!**

This bot tracks token holders and maintains a leaderboard based on how long they've held tokens.

**Available Commands:**
• `/leaderboard` - View the top token holders
• `/rank <wallet>` - Check your wallet's rank
• `/stats` - View bot statistics
• `/help` - Show this help message

**Token Contract:**
`9M7eYNNP4TdJCmMspKpdbEhvpdds6E5WFVTTLjXfVray`

The bot takes daily snapshots to track how long each wallet has held tokens. The longer you hold, the higher your rank!
        """
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
📚 **Bot Help & Commands**

**User Commands:**
• `/start` - Welcome message and bot introduction
• `/leaderboard` - View top token holders ranked by days held
• `/rank <wallet_address>` - Check specific wallet's rank
• `/stats` - View bot statistics and current snapshot info

**Admin Commands:**
• `/admin` - Access admin panel (admin only)
• `/snapshot` - Manually trigger a snapshot (admin only)

**How It Works:**
1. Bot takes daily snapshots of all token holders
2. Each day a wallet holds tokens, their "days_held" increases
3. Leaderboard ranks wallets by days held (highest first)
4. Only wallets above minimum USD threshold are shown

**Example Usage:**
• `/rank 9M7eYNNP4TdJCmMspKpdbEhvpdds6E5WFVTTLjXfVray`
• `/leaderboard` - Shows top 50 holders
        """
        
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /leaderboard command"""
        try:
            # Get leaderboard data
            leaderboard = self.db.get_leaderboard(limit=50)
            
            if not leaderboard:
                await update.message.reply_text("❌ No leaderboard data available yet.")
                return
            
            # Format leaderboard message
            message = "🏆 **Token Holder Leaderboard**\n\n"
            message += f"*Ranked by days held (minimum ${self.db.get_minimum_usd_threshold():.2f} USD)*\n\n"
            
            for i, holder in enumerate(leaderboard, 1):
                wallet = holder['wallet_address']
                days_held = holder['days_held']
                usd_value = holder['usd_value'] or 0
                token_balance = holder['token_balance'] or 0
                
                # Truncate wallet address for display
                display_wallet = f"{wallet[:8]}...{wallet[-8:]}"
                
                message += f"**{i}.** {display_wallet}\n"
                message += f"   📅 {days_held} days | 💰 ${usd_value:,.2f} | 🪙 {token_balance:,.2f}\n\n"
            
            message += f"\n📊 Total holders: {self.db.get_total_holders()}"
            
            # Split message if too long
            if len(message) > 4096:
                parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
                for part in parts:
                    await update.message.reply_text(part, parse_mode='Markdown')
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            await update.message.reply_text("❌ Error fetching leaderboard. Please try again later.")
    
    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /rank command"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "❌ Please provide a wallet address.\n"
                    "Usage: `/rank <wallet_address>`"
                )
                return
            
            wallet_address = context.args[0]
            
            # Validate wallet address
            if not self.solscan.validate_wallet_address(wallet_address):
                await update.message.reply_text("❌ Invalid Solana wallet address.")
                return
            
            # Get holder rank
            rank, days_held = self.db.get_holder_rank(wallet_address)
            
            if rank is None:
                await update.message.reply_text(
                    "❌ Wallet not found in leaderboard.\n"
                    "This could mean:\n"
                    "• Wallet doesn't hold tokens\n"
                    "• Wallet value is below minimum threshold\n"
                    "• Wallet hasn't been snapshotted yet"
                )
                return
            
            # Get holder details
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT token_balance, usd_value, first_seen_date 
                    FROM holders WHERE wallet_address = %s
                """, (wallet_address,))
                result = cursor.fetchone()
            
            if result:
                token_balance, usd_value, first_seen_date = result
                
                message = f"📊 **Wallet Rank Information**\n\n"
                message += f"**Wallet:** `{wallet_address}`\n"
                message += f"**Rank:** #{rank}\n"
                message += f"**Days Held:** {days_held} days\n"
                message += f"**Token Balance:** {token_balance:,.2f}\n"
                message += f"**USD Value:** ${usd_value:,.2f}\n"
                message += f"**First Seen:** {first_seen_date}\n"
                message += f"**Minimum Threshold:** ${self.db.get_minimum_usd_threshold():.2f}"
                
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Error fetching wallet details.")
                
        except Exception as e:
            logger.error(f"Error in rank command: {e}")
            await update.message.reply_text("❌ Error fetching rank. Please try again later.")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            stats = self.snapshot_service.get_snapshot_stats()
            
            if not stats:
                await update.message.reply_text("❌ No statistics available yet.")
                return
            
            message = "📊 **Bot Statistics**\n\n"
            message += f"**Total Holders:** {stats['total_holders']:,}\n"
            message += f"**Minimum USD Threshold:** ${stats['minimum_usd_threshold']:,.2f}\n"
            message += f"**Last Snapshot:** {stats['snapshot_date']}\n\n"
            
            if stats['top_holders']:
                message += "**Top 5 Holders:**\n"
                for i, holder in enumerate(stats['top_holders'][:5], 1):
                    wallet = holder['wallet_address']
                    days_held = holder['days_held']
                    usd_value = holder['usd_value'] or 0
                    
                    display_wallet = f"{wallet[:8]}...{wallet[-8:]}"
                    message += f"{i}. {display_wallet} - {days_held} days (${usd_value:,.2f})\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text("❌ Error fetching statistics. Please try again later.")
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_USER_IDS:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return
        
        # Create admin panel keyboard
        keyboard = [
            [InlineKeyboardButton("📊 View Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("💰 Set USD Threshold", callback_data="set_threshold")],
            [InlineKeyboardButton("📸 Manual Snapshot", callback_data="manual_snapshot")],
            [InlineKeyboardButton("🧹 Cleanup Old Data", callback_data="cleanup_data")],
            [InlineKeyboardButton("✅ Validate Data", callback_data="validate_data")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔧 **Admin Panel**\n\nSelect an option:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def snapshot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /snapshot command (admin only)"""
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_USER_IDS:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return
        
        await update.message.reply_text("📸 Starting manual snapshot... This may take a few minutes.")
        
        # Run snapshot in background
        asyncio.create_task(self._run_snapshot(update, context))
    
    async def _run_snapshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run snapshot in background and notify user"""
        try:
            success = self.snapshot_service.take_daily_snapshot()
            
            if success:
                await update.message.reply_text("✅ Manual snapshot completed successfully!")
            else:
                await update.message.reply_text("❌ Manual snapshot failed. Check logs for details.")
                
        except Exception as e:
            logger.error(f"Error in manual snapshot: {e}")
            await update.message.reply_text(f"❌ Error during snapshot: {str(e)}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks from admin panel"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id not in Config.ADMIN_USER_IDS:
            await query.edit_message_text("❌ Access denied.")
            return
        
        if query.data == "admin_stats":
            await self._handle_admin_stats(query)
        elif query.data == "set_threshold":
            await self._handle_set_threshold(query)
        elif query.data == "manual_snapshot":
            await self._handle_manual_snapshot(query)
        elif query.data == "cleanup_data":
            await self._handle_cleanup_data(query)
        elif query.data == "validate_data":
            await self._handle_validate_data(query)
    
    async def _handle_admin_stats(self, query):
        """Handle admin stats button"""
        try:
            stats = self.snapshot_service.get_snapshot_stats()
            validation = self.snapshot_service.validate_snapshot_data()
            
            message = "📊 **Admin Statistics**\n\n"
            message += f"**Total Holders:** {stats['total_holders']:,}\n"
            message += f"**Minimum USD Threshold:** ${stats['minimum_usd_threshold']:,.2f}\n"
            message += f"**Data Validation:** {'✅ Valid' if validation['is_valid'] else '❌ Issues Found'}\n"
            
            if not validation['is_valid']:
                message += f"**Issues:** {validation.get('holders_without_snapshots', 0)} holders without snapshots, "
                message += f"{validation.get('orphaned_snapshots', 0)} orphaned snapshots\n"
            
            await query.edit_message_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in admin stats: {e}")
            await query.edit_message_text("❌ Error fetching admin stats.")
    
    async def _handle_set_threshold(self, query):
        """Handle set threshold button"""
        await query.edit_message_text(
            "💰 **Set Minimum USD Threshold**\n\n"
            "Current threshold: ${:.2f}\n\n"
            "To change the threshold, use:\n"
            "/set_threshold <amount>\n\n"
            "Example: /set_threshold 100",
            parse_mode='Markdown'
        )
    
    async def _handle_manual_snapshot(self, query):
        """Handle manual snapshot button"""
        await query.edit_message_text("📸 Starting manual snapshot... This may take a few minutes.")
        
        # Run snapshot in background
        asyncio.create_task(self._run_admin_snapshot(query))
    
    async def _run_admin_snapshot(self, query):
        """Run snapshot for admin panel"""
        try:
            success = self.snapshot_service.take_daily_snapshot()
            
            if success:
                await query.edit_message_text("✅ Manual snapshot completed successfully!")
            else:
                await query.edit_message_text("❌ Manual snapshot failed. Check logs for details.")
                
        except Exception as e:
            logger.error(f"Error in admin snapshot: {e}")
            await query.edit_message_text(f"❌ Error during snapshot: {str(e)}")
    
    async def _handle_cleanup_data(self, query):
        """Handle cleanup data button"""
        try:
            deleted_count = self.snapshot_service.cleanup_old_snapshots()
            
            message = f"🧹 **Data Cleanup Completed**\n\n"
            message += f"**Deleted snapshots:** {deleted_count} (older than 90 days)\n"
            message += "This helps maintain database performance."
            
            await query.edit_message_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            await query.edit_message_text("❌ Error during cleanup.")
    
    async def _handle_validate_data(self, query):
        """Handle validate data button"""
        try:
            validation = self.snapshot_service.validate_snapshot_data()
            
            message = "✅ **Data Validation Results**\n\n"
            
            if validation['is_valid']:
                message += "**Status:** All data is valid! 🎉\n"
            else:
                message += "**Status:** Issues found ❌\n"
                message += f"**Holders without snapshots:** {validation.get('holders_without_snapshots', 0)}\n"
                message += f"**Orphaned snapshots:** {validation.get('orphaned_snapshots', 0)}\n"
            
            await query.edit_message_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in validation: {e}")
            await query.edit_message_text("❌ Error during validation.")
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Token Holder Bot...")
        self.application.run_polling()
    
    def stop(self):
        """Stop the bot and close connections"""
        logger.info("Stopping Token Holder Bot...")
        self.snapshot_service.close()
        self.db.close()

if __name__ == "__main__":
    # Validate configuration
    try:
        Config.validate()
        bot = TokenHolderBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        exit(1)
