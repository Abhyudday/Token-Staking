"""Blockchain monitoring service."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .tatum_client import TatumClient
from database import get_db_manager
from config import config

logger = logging.getLogger(__name__)


class BlockchainMonitor:
    """Service for monitoring blockchain for token transactions."""
    
    def __init__(self):
        self.tatum = TatumClient()
        self.db_manager = None
        self.monitoring = False
        self.last_checked_block = None
    
    async def initialize(self):
        """Initialize the monitor."""
        self.db_manager = await get_db_manager()
        
        # Get last checked block from database settings
        last_block_str = await self.db_manager.get_setting("last_checked_block")
        if last_block_str:
            self.last_checked_block = int(last_block_str)
        else:
            # Start from current block
            self.last_checked_block = await self.tatum.get_latest_block_number()
            if self.last_checked_block:
                await self.db_manager.set_setting(
                    "last_checked_block", 
                    str(self.last_checked_block),
                    "Last blockchain block checked for transactions"
                )
    
    async def start_monitoring(self, interval_seconds: int = 300):
        """Start monitoring blockchain for new transactions."""
        if self.monitoring:
            logger.warning("Monitoring is already running")
            return
        
        self.monitoring = True
        logger.info(f"Starting blockchain monitoring (interval: {interval_seconds}s)")
        
        while self.monitoring:
            try:
                await self.check_for_new_transactions()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)
    
    def stop_monitoring(self):
        """Stop monitoring blockchain."""
        self.monitoring = False
        logger.info("Stopped blockchain monitoring")
    
    async def check_for_new_transactions(self):
        """Check for new token transactions since last check."""
        try:
            current_block = await self.tatum.get_latest_block_number()
            if not current_block:
                logger.warning("Could not get current block number")
                return
            
            if not self.last_checked_block:
                self.last_checked_block = current_block - 100  # Start from 100 blocks ago
            
            # Get new token holders and transactions
            new_holders = await self.tatum.monitor_token_holders(self.last_checked_block)
            
            for holder_data in new_holders:
                await self.process_new_holder(holder_data)
            
            # Update last checked block
            self.last_checked_block = current_block
            await self.db_manager.set_setting("last_checked_block", str(current_block))
            
            if new_holders:
                logger.info(f"Processed {len(new_holders)} new transactions up to block {current_block}")
            
        except Exception as e:
            logger.error(f"Error checking for new transactions: {e}")
    
    async def process_new_holder(self, holder_data: Dict[str, Any]):
        """Process a new token holder or transaction."""
        try:
            wallet_address = holder_data["wallet_address"]
            amount = holder_data["amount"]
            tx_hash = holder_data["transaction_hash"]
            block_number = holder_data["block_number"]
            timestamp = holder_data["timestamp"]
            
            # Get current balance for this wallet
            current_balance = await self.tatum.get_token_balance(wallet_address)
            if current_balance is None:
                logger.warning(f"Could not get balance for wallet {wallet_address}")
                current_balance = amount
            
            # Create or update holder
            holder = await self.db_manager.create_or_update_holder(
                wallet_address=wallet_address,
                current_balance=current_balance
            )
            
            # Add transaction
            transaction = await self.db_manager.add_transaction(
                holder_id=holder.id,
                transaction_hash=tx_hash,
                transaction_type="buy",  # Assuming new holders are buying
                amount=amount,
                block_number=block_number,
                timestamp=timestamp
            )
            
            if transaction:
                logger.info(f"New holder transaction: {wallet_address[:8]}... bought {amount} tokens")
            
        except Exception as e:
            logger.error(f"Error processing new holder {holder_data}: {e}")
    
    async def update_all_balances(self):
        """Update balances for all known holders."""
        try:
            # Get all holders from database
            async with self.db_manager.get_session() as session:
                from database.models import Holder
                from sqlalchemy import select
                
                result = await session.execute(select(Holder))
                holders = result.scalars().all()
            
            logger.info(f"Updating balances for {len(holders)} holders")
            
            for holder in holders:
                try:
                    # Get current balance from blockchain
                    current_balance = await self.tatum.get_token_balance(holder.wallet_address)
                    
                    if current_balance is not None:
                        # Update holder's balance
                        await self.db_manager.create_or_update_holder(
                            wallet_address=holder.wallet_address,
                            telegram_user_id=holder.telegram_user_id,
                            telegram_username=holder.telegram_username,
                            current_balance=current_balance
                        )
                        
                        # Check if they sold (balance is 0 or very low)
                        if current_balance < 0.001 and holder.is_eligible:
                            # Mark as ineligible
                            async with self.db_manager.get_session() as session:
                                from database.models import Holder
                                from sqlalchemy import select
                                
                                result = await session.execute(
                                    select(Holder).where(Holder.id == holder.id)
                                )
                                db_holder = result.scalar_one()
                                db_holder.is_eligible = False
                                db_holder.current_balance = current_balance
                                
                                logger.info(f"Holder {holder.wallet_address[:8]}... sold tokens, marked ineligible")
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error updating balance for {holder.wallet_address}: {e}")
            
            logger.info("Finished updating all balances")
            
        except Exception as e:
            logger.error(f"Error in update_all_balances: {e}")
    
    async def check_holder_eligibility(self, wallet_address: str) -> Dict[str, Any]:
        """Check if a holder is eligible for rewards."""
        try:
            holder = await self.db_manager.get_holder_by_wallet(wallet_address)
            if not holder:
                return {
                    "eligible": False,
                    "reason": "Wallet not found in database",
                    "days_held": 0,
                    "days_remaining": config.MINIMUM_HOLD_DAYS
                }
            
            # Get current balance from blockchain
            current_balance = await self.tatum.get_token_balance(wallet_address)
            
            if current_balance is None or current_balance < 0.001:
                return {
                    "eligible": False,
                    "reason": "No tokens held",
                    "days_held": holder.holding_days,
                    "days_remaining": max(0, config.MINIMUM_HOLD_DAYS - holder.holding_days)
                }
            
            if not holder.is_eligible:
                return {
                    "eligible": False,
                    "reason": "Previously sold tokens",
                    "days_held": holder.holding_days,
                    "days_remaining": 0
                }
            
            days_remaining = max(0, config.MINIMUM_HOLD_DAYS - holder.holding_days)
            
            return {
                "eligible": holder.is_eligible_for_reward,
                "reason": "Eligible for rewards" if holder.is_eligible_for_reward else f"Need to hold for {days_remaining} more days",
                "days_held": holder.holding_days,
                "days_remaining": days_remaining,
                "current_balance": float(current_balance),
                "first_buy_date": holder.first_buy_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking eligibility for {wallet_address}: {e}")
            return {
                "eligible": False,
                "reason": "Error checking eligibility",
                "days_held": 0,
                "days_remaining": config.MINIMUM_HOLD_DAYS
            }
    
    async def get_transaction_history(self, wallet_address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get transaction history for a wallet."""
        try:
            holder = await self.db_manager.get_holder_by_wallet(wallet_address)
            if not holder:
                return []
            
            # Get transactions from database
            async with self.db_manager.get_session() as session:
                from database.models import Transaction
                from sqlalchemy import select, desc
                
                result = await session.execute(
                    select(Transaction)
                    .where(Transaction.holder_id == holder.id)
                    .order_by(desc(Transaction.timestamp))
                    .limit(limit)
                )
                transactions = result.scalars().all()
            
            transaction_list = []
            for tx in transactions:
                transaction_list.append({
                    "hash": tx.transaction_hash,
                    "type": tx.transaction_type,
                    "amount": float(tx.amount),
                    "price_usd": float(tx.price_usd) if tx.price_usd else None,
                    "timestamp": tx.timestamp.isoformat(),
                    "block_number": tx.block_number
                })
            
            return transaction_list
            
        except Exception as e:
            logger.error(f"Error getting transaction history for {wallet_address}: {e}")
            return []
    
    async def sync_wallet_transactions(self, wallet_address: str):
        """Sync all transactions for a specific wallet."""
        try:
            # Get transactions from blockchain
            blockchain_txs = await self.tatum.get_token_transactions(wallet_address)
            
            if not blockchain_txs:
                logger.info(f"No transactions found for wallet {wallet_address}")
                return
            
            # Get or create holder
            current_balance = await self.tatum.get_token_balance(wallet_address)
            holder = await self.db_manager.create_or_update_holder(
                wallet_address=wallet_address,
                current_balance=current_balance or 0.0
            )
            
            # Add each transaction
            for tx in blockchain_txs:
                await self.db_manager.add_transaction(
                    holder_id=holder.id,
                    transaction_hash=tx["hash"],
                    transaction_type=tx["type"],
                    amount=tx["amount"],
                    block_number=tx["block_number"],
                    timestamp=tx["timestamp"]
                )
            
            logger.info(f"Synced {len(blockchain_txs)} transactions for wallet {wallet_address}")
            
        except Exception as e:
            logger.error(f"Error syncing transactions for {wallet_address}: {e}")
    
    async def close(self):
        """Close the monitor and cleanup resources."""
        self.stop_monitoring()
        await self.tatum.close()
