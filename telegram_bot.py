import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from database import Database
from snapshot_service import SnapshotService
from helius_api import HeliusAPI
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
        self.helius = HeliusAPI()
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
            logger.info(f"Leaderboard command requested by user {update.effective_user.id}")
            
            # Get leaderboard data
            logger.info("Fetching leaderboard data from database...")
            leaderboard = self.db.get_leaderboard(limit=50)
            logger.info(f"Leaderboard query returned {len(leaderboard) if leaderboard else 0} results")
            
            if not leaderboard:
                logger.warning("No leaderboard data available - this could mean:")
                logger.warning("- Database is empty")
                logger.warning("- No snapshots have been taken yet")
                logger.warning("- All holders are below minimum USD threshold")
                await update.message.reply_text("❌ No leaderboard data available yet.")
                return
            
            # Format leaderboard message
            logger.info("Formatting leaderboard message...")
            message = "🏆 **Token Holder Leaderboard**\n\n"
            message += f"*Ranked by days held (minimum ${self.db.get_minimum_usd_threshold():.2f} USD)*\n\n"
            
            for i, holder in enumerate(leaderboard, 1):
                wallet = holder['wallet_address']
                days_held = holder['days_held']
                usd_value = holder['usd_value'] or 0
                token_balance = holder['token_balance'] or 0
                
                # Show full wallet address
                display_wallet = wallet
                
                message += f"**{i}.** {display_wallet}\n"
                message += f"   📅 {days_held} days | 💰 ${usd_value:,.2f} | 🪙 {token_balance:,.2f}\n\n"
            
            message += f"\n📊 Total holders: {self.db.get_total_holders()}"
            
            # Split message if too long
            if len(message) > 4096:
                logger.info(f"Message too long ({len(message)} chars), splitting into parts...")
                parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
                logger.info(f"Split into {len(parts)} parts")
                for i, part in enumerate(parts):
                    await update.message.reply_text(part, parse_mode='Markdown')
                    logger.info(f"Sent part {i+1}/{len(parts)}")
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
                logger.info(f"Sent leaderboard message ({len(message)} chars)")
                
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            await update.message.reply_text("❌ Error fetching leaderboard. Please try again later.")
    
    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /rank command"""
        try:
            logger.info(f"Rank command requested by user {update.effective_user.id}")
            
            if not context.args:
                logger.warning("Rank command called without wallet address")
                await update.message.reply_text(
                    "❌ Please provide a wallet address.\n"
                    "Usage: `/rank <wallet_address>`"
                )
                return
            
            wallet_address = context.args[0]
            logger.info(f"Checking rank for wallet: {wallet_address[:8]}...{wallet_address[-8:]}")
            
            # Validate wallet address
            if not self.helius.validate_wallet_address(wallet_address):
                logger.warning(f"Invalid wallet address provided: {wallet_address}")
                await update.message.reply_text("❌ Invalid Solana wallet address.")
                return
            
            # Get holder rank
            logger.info("Fetching holder rank from database...")
            rank, days_held = self.db.get_holder_rank(wallet_address)
            logger.info(f"Rank query result: rank={rank}, days_held={days_held}")
            
            if rank is None:
                logger.warning(f"Wallet not found in leaderboard: {wallet_address[:8]}...{wallet_address[-8:]}")
                await update.message.reply_text(
                    "❌ Wallet not found in leaderboard.\n"
                    "This could mean:\n"
                    "• Wallet doesn't hold tokens\n"
                    "• Wallet value is below minimum threshold\n"
                    "• Wallet hasn't been snapshotted yet"
                )
                return
            
            # Get holder details
            logger.info("Fetching holder details...")
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT token_balance, usd_value, first_seen_date 
                    FROM holders WHERE wallet_address = %s
                """, (wallet_address,))
                result = cursor.fetchone()
            
            if result:
                token_balance, usd_value, first_seen_date = result
                logger.info(f"Holder details: balance={token_balance}, usd_value={usd_value}, first_seen={first_seen_date}")
                
                message = f"📊 **Wallet Rank Information**\n\n"
                message += f"**Wallet:** `{wallet_address}`\n"
                message += f"**Rank:** #{rank}\n"
                message += f"**Days Held:** {days_held} days\n"
                message += f"**Token Balance:** {token_balance:,.2f}\n"
                message += f"**USD Value:** ${usd_value:,.2f}\n"
                message += f"**First Seen:** {first_seen_date}\n"
                message += f"**Minimum Threshold:** ${self.db.get_minimum_usd_threshold():.2f}"
                
                await update.message.reply_text(message, parse_mode='Markdown')
                logger.info(f"Rank information sent successfully for wallet {wallet_address[:8]}...{wallet_address[-8:]}")
            else:
                logger.error(f"Failed to fetch holder details for wallet: {wallet_address[:8]}...{wallet_address[-8:]}")
                await update.message.reply_text("❌ Error fetching wallet details.")
                
        except Exception as e:
            logger.error(f"Error in rank command: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            await update.message.reply_text("❌ Error fetching rank. Please try again later.")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            logger.info(f"Stats command requested by user {update.effective_user.id}")
            
            logger.info("Fetching snapshot statistics...")
            stats = self.snapshot_service.get_snapshot_stats()
            logger.info(f"Stats service returned: {stats}")
            
            if not stats:
                logger.warning("No statistics available from snapshot service")
                await update.message.reply_text("❌ No statistics available yet.")
                return
            
            message = "📊 **Bot Statistics**\n\n"
            message += f"**Total Holders:** {stats['total_holders']:,}\n"
            message += f"**Minimum USD Threshold:** ${stats['minimum_usd_threshold']:,.2f}\n"
            message += f"**Last Snapshot:** {stats['snapshot_date']}\n\n"
            
            if stats['top_holders']:
                logger.info(f"Found {len(stats['top_holders'])} top holders")
                message += "**Top 5 Holders:**\n"
                for i, holder in enumerate(stats['top_holders'][:5], 1):
                    wallet = holder['wallet_address']
                    days_held = holder['days_held']
                    usd_value = holder['usd_value'] or 0
                    
                    display_wallet = f"{wallet[:8]}...{wallet[-8:]}"
                    message += f"{i}. {display_wallet} - {days_held} days (${usd_value:,.2f})\n"
            else:
                logger.warning("No top holders in stats")
                message += "**Top Holders:** No data available\n"
            
            logger.info(f"Sending stats message ({len(message)} chars)")
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            await update.message.reply_text("❌ Error fetching statistics. Please try again later.")
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        try:
            logger.info(f"Admin command requested by user {update.effective_user.id}")
            
            # Check if user is admin
            if not self._is_admin(update.effective_user.id):
                logger.warning(f"Non-admin user {update.effective_user.id} attempted to access admin panel")
                await update.message.reply_text("❌ Access denied. Admin privileges required.")
                return
            
            # Create admin panel with inline keyboard
            keyboard = [
                [InlineKeyboardButton("💰 Set Min USD Threshold", callback_data="admin_set_threshold")],
                [InlineKeyboardButton("📊 View Bot Stats", callback_data="admin_view_stats")],
                [InlineKeyboardButton("🔄 Manual Snapshot", callback_data="admin_manual_snapshot")],
                [InlineKeyboardButton("💵 Set Token Price", callback_data="admin_set_price")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            current_threshold = self.db.get_minimum_usd_threshold()
            message = f"🔧 **Admin Panel**\n\n"
            message += f"Current minimum USD threshold: **${current_threshold:.2f}**\n"
            message += f"Token contract: `{self.token_address}`\n\n"
            message += "Select an option:"
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"Admin panel displayed for user {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error in admin command: {e}")
            await update.message.reply_text("❌ Error accessing admin panel. Please try again later.")
    
    async def snapshot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /snapshot command (admin only)"""
        user_id = update.effective_user.id
        logger.info(f"Snapshot command requested by user {user_id}")
        
        if user_id not in Config.ADMIN_USER_IDS:
            logger.warning(f"Unauthorized snapshot attempt by user {user_id}")
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return
        
        logger.info(f"Manual snapshot initiated by admin user {user_id}")
        await update.message.reply_text("📸 Starting manual snapshot... This may take a few minutes.")
        
        # Run snapshot in background
        asyncio.create_task(self._run_snapshot(update, context))
    
    async def _run_snapshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run snapshot in background and notify user"""
        try:
            logger.info("Starting manual snapshot process...")
            success = self.snapshot_service.take_daily_snapshot()
            
            if success:
                logger.info("Manual snapshot completed successfully")
                await update.message.reply_text("✅ Manual snapshot completed successfully!")
            else:
                logger.error("Manual snapshot failed")
                await update.message.reply_text("❌ Manual snapshot failed. Check logs for details.")
                
        except Exception as e:
            logger.error(f"Error in manual snapshot: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            await update.message.reply_text(f"❌ Error during snapshot: {str(e)}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks from admin panel"""
        query = update.callback_query
        user_id = update.effective_user.id
        logger.info(f"Button callback from user {user_id}: {query.data}")
        
        await query.answer()
        
        if user_id not in Config.ADMIN_USER_IDS:
            logger.warning(f"Unauthorized button callback from user {user_id}")
            await query.edit_message_text("❌ Access denied.")
            return
        
        logger.info(f"Processing admin button: {query.data}")
        
        if query.data == "admin_set_threshold":
            logger.info("Routing to admin set threshold handler")
            await self._handle_admin_set_threshold(query)
        elif query.data == "admin_view_stats":
            logger.info("Routing to admin view stats handler")
            await self._handle_admin_view_stats(update, context)
        elif query.data == "admin_manual_snapshot":
            logger.info("Routing to admin manual snapshot handler")
            await self._handle_admin_manual_snapshot(update, context)
        elif query.data == "admin_set_price":
            logger.info("Routing to admin set price handler")
            await self._handle_admin_set_price(update, context)
        else:
            logger.warning(f"Unknown callback data: {query.data}")
            await query.answer("Unknown option selected")
    
    async def _handle_admin_stats(self, query):
        """Handle admin stats button"""
        try:
            logger.info("Admin stats button clicked")
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
            logger.info("Admin stats displayed successfully")
            
        except Exception as e:
            logger.error(f"Error in admin stats: {e}")
            await query.edit_message_text("❌ Error fetching admin stats.")
    
    async def _handle_admin_set_threshold(self, query):
        """Handle admin set threshold button"""
        try:
            logger.info("Admin set threshold button clicked")
            current_threshold = self.db.get_minimum_usd_threshold()
            logger.info(f"Current threshold: ${current_threshold}")
            
            await query.edit_message_text(
                "💰 **Set Minimum USD Threshold**\n\n"
                f"Current threshold: **${current_threshold:.2f}**\n\n"
                "To change the threshold, use:\n"
                "`/set_threshold <amount>`\n\n"
                "**Example:** `/set_threshold 100`\n\n"
                "This will filter the leaderboard to show only holders with at least this USD value.",
                parse_mode='Markdown'
            )
            logger.info("Admin threshold info displayed")
            
        except Exception as e:
            logger.error(f"Error in admin set threshold: {e}")
            await query.edit_message_text("❌ Error displaying threshold info")
    
    async def _handle_set_threshold(self, query):
        """Handle set threshold button"""
        logger.info("Set threshold button clicked")
        current_threshold = self.db.get_minimum_usd_threshold()
        logger.info(f"Current threshold: ${current_threshold}")
        
        await query.edit_message_text(
            "💰 **Set Minimum USD Threshold**\n\n"
            f"Current threshold: ${current_threshold:.2f}\n\n"
            "To change the threshold, use:\n"
            "/set_threshold <amount>\n\n"
            "Example: /set_threshold 100",
            parse_mode='Markdown'
        )
    
    async def _handle_manual_snapshot(self, query):
        """Handle manual snapshot button"""
        logger.info("Manual snapshot button clicked")
        await query.edit_message_text("📸 Starting manual snapshot... This may take a few minutes.")
        
        # Run snapshot in background
        asyncio.create_task(self._run_admin_snapshot(query))
    
    async def _run_admin_snapshot(self, query):
        """Run snapshot for admin panel"""
        try:
            logger.info("Starting admin panel snapshot...")
            success = self.snapshot_service.take_daily_snapshot()
            
            if success:
                logger.info("Admin panel snapshot completed successfully")
                await query.edit_message_text("✅ Manual snapshot completed successfully!")
            else:
                logger.error("Admin panel snapshot failed")
                await query.edit_message_text("❌ Manual snapshot failed. Check logs for details.")
                
        except Exception as e:
            logger.error(f"Error in admin snapshot: {e}")
            await query.edit_message_text(f"❌ Error during snapshot: {str(e)}")
    
    async def _handle_cleanup_data(self, query):
        """Handle cleanup data button"""
        try:
            logger.info("Cleanup data button clicked")
            deleted_count = self.snapshot_service.cleanup_old_snapshots()
            
            message = f"🧹 **Data Cleanup Completed**\n\n"
            message += f"**Deleted snapshots:** {deleted_count} (older than 90 days)\n"
            message += "This helps maintain database performance."
            
            await query.edit_message_text(message, parse_mode='Markdown')
            logger.info(f"Data cleanup completed, deleted {deleted_count} snapshots")
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            await query.edit_message_text("❌ Error during cleanup.")
    
    async def _handle_validate_data(self, query):
        """Handle validate data button"""
        try:
            logger.info("Validate data button clicked")
            validation = self.snapshot_service.validate_snapshot_data()
            
            message = "✅ **Data Validation Results**\n\n"
            
            if validation['is_valid']:
                message += "**Status:** All data is valid! 🎉\n"
                logger.info("Data validation passed")
            else:
                message += "**Status:** Issues found ❌\n"
                message += f"**Holders without snapshots:** {validation.get('holders_without_snapshots', 0)}\n"
                message += f"**Orphaned snapshots:** {validation.get('orphaned_snapshots', 0)}\n"
                logger.warning(f"Data validation failed: {validation}")
            
            await query.edit_message_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in validation: {e}")
            await query.edit_message_text("❌ Error during validation.")
    
    async def _handle_admin_set_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin setting token price"""
        try:
            message = "💵 **Set Token Price**\n\n"
            message += "Please send the token price in USD.\n"
            message += "Example: `0.00000123` or `1.23`\n\n"
            message += "This will be used for USD calculations until the next snapshot."
            
            # Store state for price input
            context.user_data['awaiting_price_input'] = True
            
            await update.callback_query.edit_message_text(message, parse_mode='Markdown')
            logger.info("Admin price input requested")
            
        except Exception as e:
            logger.error(f"Error in admin set price: {e}")
            await update.callback_query.answer("Error setting price")
    
    async def _handle_admin_manual_snapshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin manual snapshot"""
        try:
            await update.callback_query.answer("Starting manual snapshot...")
            
            # Start snapshot in background
            import threading
            snapshot_thread = threading.Thread(target=self.snapshot_service.take_daily_snapshot)
            snapshot_thread.start()
            
            await update.callback_query.edit_message_text(
                "🔄 **Manual Snapshot Started**\n\n"
                "Snapshot is running in the background.\n"
                "Check logs for progress updates."
            )
            logger.info("Manual snapshot started by admin")
            
        except Exception as e:
            logger.error(f"Error starting manual snapshot: {e}")
            await update.callback_query.answer("Error starting snapshot")
    
    async def _handle_admin_view_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin viewing bot stats"""
        try:
            stats = self.db.get_bot_stats()
            
            message = "📊 **Bot Statistics**\n\n"
            message += f"**Total Holders:** {stats.get('total_holders', 0)}\n"
            message += f"**Total Snapshots:** {stats.get('total_snapshots', 0)}\n"
            message += f"**Last Snapshot:** {stats.get('last_snapshot', 'Never')}\n"
            message += f"**Min USD Threshold:** ${stats.get('min_usd_threshold', 0):.2f}\n"
            message += f"**Database Size:** {stats.get('db_size', 'Unknown')}\n"
            
            await update.callback_query.edit_message_text(message, parse_mode='Markdown')
            logger.info("Admin stats displayed")
            
        except Exception as e:
            logger.error(f"Error displaying admin stats: {e}")
            await update.callback_query.answer("Error displaying stats")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        try:
            # Check if admin is setting price
            if context.user_data.get('awaiting_price_input') and self._is_admin(update.effective_user.id):
                await self._handle_price_input(update, context)
                return
            
            # Ignore other messages
            return
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_price_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin price input"""
        try:
            price_text = update.message.text.strip()
            
            # Validate price input
            try:
                price = float(price_text)
                if price <= 0:
                    await update.message.reply_text("❌ Price must be greater than 0.")
                    return
            except ValueError:
                await update.message.reply_text("❌ Invalid price format. Please send a number like `0.00000123`")
                return
            
            # Store the price for next snapshot
            context.user_data['manual_token_price'] = price
            context.user_data['awaiting_price_input'] = False
            
            message = f"✅ **Token Price Set**\n\n"
            message += f"Price: **${price:.8f}**\n\n"
            message += "This price will be used for the next snapshot.\n"
            message += "Run `/snapshot` to apply the new price immediately."
            
            await update.message.reply_text(message, parse_mode='Markdown')
            logger.info(f"Admin set manual token price: ${price}")
            
        except Exception as e:
            logger.error(f"Error handling price input: {e}")
            await update.message.reply_text("❌ Error setting price. Please try again.")
            context.user_data['awaiting_price_input'] = False
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in Config.ADMIN_USER_IDS
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Token Holder Bot...")
        try:
            # Run the bot in the current event loop
            self.application.run_polling()
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
    
    def stop(self):
        """Stop the bot and close connections"""
        logger.info("Stopping Token Holder Bot...")
        try:
            # Stop the application
            if hasattr(self.application, 'stop'):
                self.application.stop()
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
        finally:
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
