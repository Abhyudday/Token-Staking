"""Blockchain monitoring service using Bitquery API."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .bitquery_client import BitqueryClient
from database import get_db_manager
from config import config

logger = logging.getLogger(__name__)


class BitqueryMonitor:
    """Service for monitoring blockchain using Bitquery API."""
    
    def __init__(self):
        self.bitquery = BitqueryClient()
        self.db_manager = None
        self.monitoring = False
        self.last_sync_time = None
    
    async def initialize(self):
        """Initialize the monitor."""
        try:
            self.db_manager = await get_db_manager()
            
            # Get last sync time from database settings
            last_sync_str = await self.db_manager.get_setting("last_bitquery_sync")
            if last_sync_str:
                try:
                    self.last_sync_time = datetime.fromisoformat(last_sync_str)
                except:
                    self.last_sync_time = None
            
            if not self.last_sync_time:
                # Start from 7 days ago
                self.last_sync_time = datetime.now(timezone.utc) - timedelta(days=7)
                
        except Exception as e:
            logger.warning(f"Database initialization failed for Bitquery monitor: {e}")
            self.db_manager = None
            # Start from 7 days ago without database
            self.last_sync_time = datetime.now(timezone.utc) - timedelta(days=7)
    
    async def start_monitoring(self, interval_seconds: int = 1800):  # 30 minutes
        """Start monitoring blockchain for token holders."""
        if self.monitoring:
            logger.warning("Bitquery monitoring is already running")
            return
        
        self.monitoring = True
        logger.info(f"Starting Bitquery monitoring (interval: {interval_seconds}s)")
        
        while self.monitoring:
            try:
                await self.sync_token_holders()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error in Bitquery monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)
    
    def stop_monitoring(self):
        """Stop monitoring blockchain."""
        self.monitoring = False
        logger.info("Stopped Bitquery monitoring")
    
    async def sync_token_holders(self):
        """Sync token holders data from Bitquery."""
        try:
            logger.info("Syncing token holders from Bitquery...")
            
            # Get token holders with history from Bitquery
            holders_data = await self.bitquery.get_token_holders_with_history(limit=500)
            
            if not holders_data:
                logger.warning("No token holders data received from Bitquery")
                return
            
            synced_count = 0
            for holder_data in holders_data:
                if await self.process_holder_data(holder_data):
                    synced_count += 1
            
            # Update last sync time
            self.last_sync_time = datetime.now(timezone.utc)
            if self.db_manager:
                try:
                    await self.db_manager.set_setting(
                        "last_bitquery_sync", 
                        self.last_sync_time.isoformat(),
                        "Last Bitquery sync timestamp"
                    )
                except Exception as e:
                    logger.warning(f"Could not save last sync time to database: {e}")
            
            logger.info(f"Synced {synced_count} token holders from Bitquery")
            
        except Exception as e:
            logger.error(f"Error syncing token holders: {e}")
    
    async def process_holder_data(self, holder_data: Dict[str, Any]) -> bool:
        """Process and store holder data."""
        try:
            if not self.db_manager:
                logger.info(f"New holder detected (no database): {holder_data['wallet_address'][:8]}... - {holder_data['holding_days']} days")
                return True
            
            wallet_address = holder_data["wallet_address"]
            current_balance = holder_data["current_balance"]
            holding_days = holder_data["holding_days"]
            first_buy_date = holder_data["first_buy_date"]
            last_activity_date = holder_data["last_activity_date"]
            is_eligible = holder_data["is_eligible"]
            
            # Create or update holder in database
            holder = await self.db_manager.create_or_update_holder(
                wallet_address=wallet_address,
                current_balance=current_balance
            )
            
            # Update additional fields if holder was created/updated
            if holder:
                # Update holder with Bitquery data
                async with self.db_manager.get_session() as session:
                    from database.models import Holder
                    from sqlalchemy import select
                    
                    result = await session.execute(
                        select(Holder).where(Holder.wallet_address == wallet_address)
                    )
                    db_holder = result.scalar_one_or_none()
                    
                    if db_holder:
                        # Update fields based on Bitquery data
                        if first_buy_date and not db_holder.first_buy_date:
                            db_holder.first_buy_date = first_buy_date
                        
                        if last_activity_date:
                            db_holder.last_activity_date = last_activity_date
                        
                        db_holder.current_balance = current_balance
                        db_holder.is_eligible = is_eligible
                        
                        # Calculate holding days based on first buy date
                        if db_holder.first_buy_date:
                            current_time = datetime.now(timezone.utc)
                            db_holder.holding_days = (current_time - db_holder.first_buy_date).days
                
                logger.debug(f"Updated holder: {wallet_address[:8]}... - {holding_days} days, balance: {current_balance}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing holder data {holder_data}: {e}")
            return False
    
    async def get_leaderboard_by_holding_days(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get leaderboard sorted by holding days using Bitquery data."""
        try:
            # Get holders from Bitquery with their holding history
            holders_data = await self.bitquery.get_token_holders_with_history(limit=limit * 2)  # Get more to filter
            
            if not holders_data:
                return []
            
            # Filter eligible holders and sort by holding days
            eligible_holders = [
                holder for holder in holders_data 
                if holder.get("is_eligible", False) and holder.get("current_balance", 0) > 0
            ]
            
            # Sort by holding days (descending), then by balance
            eligible_holders.sort(
                key=lambda x: (x.get("holding_days", 0), x.get("current_balance", 0)), 
                reverse=True
            )
            
            # Take top N
            top_holders = eligible_holders[:limit]
            
            # Format for leaderboard
            leaderboard = []
            for i, holder in enumerate(top_holders, 1):
                leaderboard.append({
                    "rank": i,
                    "wallet_address": holder["wallet_address"],
                    "holding_days": holder["holding_days"],
                    "current_balance": holder["current_balance"],
                    "first_buy_date": holder.get("first_buy_date"),
                    "is_eligible": holder.get("is_eligible", False),
                    "transaction_count": holder.get("transaction_count", 0)
                })
            
            return leaderboard
            
        except Exception as e:
            logger.error(f"Error getting leaderboard by holding days: {e}")
            return []
    
    async def get_holder_details(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific holder."""
        try:
            # Get details from Bitquery
            holder_details = await self.bitquery.get_holder_details(wallet_address)
            
            if not holder_details:
                return None
            
            # Add eligibility check based on minimum holding days
            holding_days = holder_details.get("holding_days", 0)
            is_eligible_for_reward = (
                holder_details.get("is_eligible", False) and 
                holding_days >= config.MINIMUM_HOLD_DAYS and
                holder_details.get("current_balance", 0) > 0
            )
            
            holder_details["is_eligible_for_reward"] = is_eligible_for_reward
            holder_details["days_remaining"] = max(0, config.MINIMUM_HOLD_DAYS - holding_days)
            
            return holder_details
            
        except Exception as e:
            logger.error(f"Error getting holder details for {wallet_address}: {e}")
            return None
    
    async def update_holder_telegram_info(self, wallet_address: str, telegram_user_id: int, telegram_username: str = None):
        """Update holder's Telegram information."""
        if not self.db_manager:
            logger.warning("Cannot update holder Telegram info: no database connection")
            return
        
        try:
            await self.db_manager.create_or_update_holder(
                wallet_address=wallet_address,
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username
            )
            logger.info(f"Updated Telegram info for holder {wallet_address[:8]}...")
            
        except Exception as e:
            logger.error(f"Error updating holder Telegram info: {e}")
    
    async def close(self):
        """Close the monitor and cleanup resources."""
        self.stop_monitoring()
        await self.bitquery.close()
