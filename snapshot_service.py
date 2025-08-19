import logging
from datetime import datetime, date, timedelta
from database import Database
from helius_api import HeliusAPI
from config import Config
import asyncio
import time

logger = logging.getLogger(__name__)

class SnapshotService:
    def __init__(self):
        self.db = Database()
        self.helius = HeliusAPI()
        self.token_address = Config.TOKEN_CONTRACT_ADDRESS
    
    def take_daily_snapshot(self):
        """Take a daily snapshot of all token holders"""
        try:
            logger.info("Starting daily snapshot process...")
            
            # Get current token price
            token_price = self.helius.get_token_price_usd(self.token_address)
            if token_price == 0:
                logger.warning("Token price unavailable; proceeding with $0.00 for USD calculations")
            else:
                logger.info(f"Current token price: ${token_price}")
            
            # Get all token holders via Helius
            holders = self.helius.get_token_holders(self.token_address, page_limit=1000)
            if not holders:
                logger.error("Failed to get token holders, aborting snapshot")
                return False
            
            logger.info(f"Found {len(holders)} token holders")
            
            # Process each holder
            processed_count = 0
            for holder in holders:
                try:
                    wallet_address = holder.get("owner")
                    token_balance = float(holder.get("amount", 0))
                    
                    if not wallet_address or token_balance <= 0:
                        continue
                    
                    # Calculate USD value
                    usd_value = token_balance * (token_price or 0)
                    
                    # Get or create holder record
                    first_seen_date = self.db.upsert_holder(wallet_address, token_balance, usd_value)
                    
                    # Calculate days held
                    days_held = self._calculate_days_held(first_seen_date)
                    
                    # Add snapshot
                    if self.db.add_snapshot(wallet_address, token_balance, usd_value, days_held):
                        processed_count += 1
                    
                    # Gentle pacing
                    time.sleep(0.02)
                    
                except Exception as e:
                    logger.error(f"Error processing holder {holder.get('owner', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Daily snapshot completed. Processed {processed_count} holders.")
            return True
            
        except Exception as e:
            logger.error(f"Error during daily snapshot: {e}")
            return False
    
    def _calculate_days_held(self, first_seen_date):
        """Calculate how many days a holder has held tokens"""
        if not first_seen_date:
            return 0
        
        if isinstance(first_seen_date, str):
            first_seen_date = datetime.strptime(first_seen_date, '%Y-%m-%d').date()
        
        today = date.today()
        days_held = (today - first_seen_date).days
        
        # Ensure days_held is at least 1 for current holders
        return max(1, days_held)
    
    def get_snapshot_stats(self):
        """Get statistics about the current snapshot"""
        try:
            total_holders = self.db.get_total_holders()
            threshold = self.db.get_minimum_usd_threshold()
            
            # Get top 10 holders
            top_holders = self.db.get_leaderboard(limit=10)
            
            stats = {
                "total_holders": total_holders,
                "minimum_usd_threshold": threshold,
                "top_holders": top_holders,
                "snapshot_date": date.today().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting snapshot stats: {e}")
            return {}
    
    def cleanup_old_snapshots(self, days_to_keep=90):
        """Clean up old snapshots to save database space"""
        try:
            cutoff_date = date.today() - timedelta(days=days_to_keep)
            
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM snapshots 
                    WHERE snapshot_date < %s
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                self.db.conn.commit()
                
                logger.info(f"Cleaned up {deleted_count} old snapshots")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up old snapshots: {e}")
            self.db.conn.rollback()
            return 0
    
    def validate_snapshot_data(self):
        """Validate the integrity of snapshot data"""
        try:
            with self.db.conn.cursor() as cursor:
                # Check for holders without snapshots
                cursor.execute("""
                    SELECT COUNT(*) FROM holders h
                    LEFT JOIN snapshots s ON h.wallet_address = s.wallet_address
                    WHERE s.wallet_address IS NULL
                """)
                
                holders_without_snapshots = cursor.fetchone()[0]
                
                # Check for snapshots without holders
                cursor.execute("""
                    SELECT COUNT(*) FROM snapshots s
                    LEFT JOIN holders h ON s.wallet_address = h.wallet_address
                    WHERE h.wallet_address IS NULL
                """)
                
                orphaned_snapshots = cursor.fetchone()[0]
                
                validation_result = {
                    "holders_without_snapshots": holders_without_snapshots,
                    "orphaned_snapshots": orphaned_snapshots,
                    "is_valid": holders_without_snapshots == 0 and orphaned_snapshots == 0
                }
                
                return validation_result
                
        except Exception as e:
            logger.error(f"Error validating snapshot data: {e}")
            return {"is_valid": False, "error": str(e)}
    
    def close(self):
        """Close database connection"""
        self.db.close()
