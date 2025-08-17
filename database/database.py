"""Database connection and management."""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.exc import IntegrityError
from contextlib import asynccontextmanager

from .models import Base, Holder, Transaction, Winner, BotSettings
from config import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self):
        self.engine = None
        self.async_session = None
    
    async def initialize(self):
        """Initialize database connection and create tables."""
        try:
            # Convert postgres:// to postgresql+asyncpg://
            db_url = config.DATABASE_URL
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif not db_url.startswith("postgresql+asyncpg://"):
                db_url = f"postgresql+asyncpg://{db_url}"
            
            self.engine = create_async_engine(
                db_url,
                echo=config.ENVIRONMENT == "development",
                pool_pre_ping=True,
                pool_recycle=300
            )
            
            self.async_session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self):
        """Get async database session."""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def ping(self):
        """Test database connectivity."""
        if not self.engine:
            raise RuntimeError("Database not initialized")
        
        async with self.engine.begin() as conn:
            await conn.execute(select(1))
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
    
    # Holder operations
    async def create_or_update_holder(
        self, 
        wallet_address: str, 
        telegram_user_id: Optional[int] = None,
        telegram_username: Optional[str] = None,
        current_balance: float = 0.0
    ) -> Holder:
        """Create or update a holder record."""
        async with self.get_session() as session:
            # Check if holder exists
            result = await session.execute(
                select(Holder).where(Holder.wallet_address == wallet_address)
            )
            holder = result.scalar_one_or_none()
            
            if holder:
                # Update existing holder
                if telegram_user_id:
                    holder.telegram_user_id = telegram_user_id
                if telegram_username:
                    holder.telegram_username = telegram_username
                holder.current_balance = current_balance
                holder.last_activity_date = datetime.now(timezone.utc)
            else:
                # Create new holder
                holder = Holder(
                    wallet_address=wallet_address,
                    telegram_user_id=telegram_user_id,
                    telegram_username=telegram_username,
                    first_buy_date=datetime.now(timezone.utc),
                    last_activity_date=datetime.now(timezone.utc),
                    current_balance=current_balance
                )
                session.add(holder)
            
            await session.flush()
            await session.refresh(holder)
            return holder
    
    async def get_holder_by_wallet(self, wallet_address: str) -> Optional[Holder]:
        """Get holder by wallet address."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Holder)
                .options(selectinload(Holder.transactions))
                .where(Holder.wallet_address == wallet_address)
            )
            return result.scalar_one_or_none()
    
    async def get_holder_by_telegram_id(self, telegram_user_id: int) -> Optional[Holder]:
        """Get holder by Telegram user ID."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Holder)
                .options(selectinload(Holder.transactions))
                .where(Holder.telegram_user_id == telegram_user_id)
            )
            return result.scalar_one_or_none()
    
    async def get_eligible_holders(self) -> List[Holder]:
        """Get all holders eligible for monthly reward."""
        async with self.get_session() as session:
            min_date = datetime.now(timezone.utc).replace(day=1)  # Start of current month
            
            result = await session.execute(
                select(Holder)
                .where(
                    and_(
                        Holder.is_eligible == True,
                        Holder.current_balance > 0,
                        Holder.first_buy_date <= min_date
                    )
                )
                .order_by(desc(Holder.holding_days))
            )
            return result.scalars().all()
    
    async def get_leaderboard(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get leaderboard data."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Holder)
                .where(
                    and_(
                        Holder.current_balance > 0,
                        Holder.is_eligible == True
                    )
                )
                .order_by(desc(Holder.current_balance))
                .limit(limit)
            )
            holders = result.scalars().all()
            
            leaderboard = []
            for i, holder in enumerate(holders, 1):
                leaderboard.append({
                    "rank": i,
                    "wallet_address": holder.wallet_address,
                    "telegram_username": holder.telegram_username,
                    "holding_days": holder.holding_days,
                    "current_balance": float(holder.current_balance),
                    "is_eligible": holder.is_eligible_for_reward
                })
            
            return leaderboard
    
    async def get_holder_rank(self, holder_id: int) -> Optional[int]:
        """Get holder's rank in leaderboard."""
        async with self.get_session() as session:
            # Get holder's balance
            holder_result = await session.execute(
                select(Holder.current_balance).where(Holder.id == holder_id)
            )
            holder_balance = holder_result.scalar_one_or_none()
            
            if holder_balance is None:
                return None
            
            # Count holders with higher balance
            count_result = await session.execute(
                select(func.count(Holder.id))
                .where(
                    and_(
                        Holder.current_balance > holder_balance,
                        Holder.is_eligible == True
                    )
                )
            )
            
            return count_result.scalar() + 1
    
    # Transaction operations
    async def add_transaction(
        self,
        holder_id: int,
        transaction_hash: str,
        transaction_type: str,
        amount: float,
        price_usd: Optional[float] = None,
        block_number: int = 0,
        timestamp: Optional[datetime] = None
    ) -> Optional[Transaction]:
        """Add a new transaction."""
        async with self.get_session() as session:
            try:
                transaction = Transaction(
                    holder_id=holder_id,
                    transaction_hash=transaction_hash,
                    transaction_type=transaction_type,
                    amount=amount,
                    price_usd=price_usd,
                    block_number=block_number,
                    timestamp=timestamp or datetime.now(timezone.utc)
                )
                session.add(transaction)
                await session.flush()
                await session.refresh(transaction)
                
                # Update holder's totals
                holder_result = await session.execute(
                    select(Holder).where(Holder.id == holder_id)
                )
                holder = holder_result.scalar_one()
                
                if transaction_type == "buy":
                    holder.total_bought += amount
                    holder.current_balance += amount
                elif transaction_type == "sell":
                    holder.total_sold += amount
                    holder.current_balance -= amount
                    # Mark as ineligible if they sold
                    holder.is_eligible = False
                
                holder.last_activity_date = datetime.now(timezone.utc)
                
                return transaction
                
            except IntegrityError:
                # Transaction already exists
                logger.warning(f"Transaction {transaction_hash} already exists")
                return None
    
    # Winner operations
    async def create_winner(
        self,
        holder_id: int,
        month: int,
        year: int,
        reward_amount: Optional[str] = None
    ) -> Winner:
        """Create a new winner record."""
        async with self.get_session() as session:
            # Get holder data at time of selection
            holder_result = await session.execute(
                select(Holder).where(Holder.id == holder_id)
            )
            holder = holder_result.scalar_one()
            
            winner = Winner(
                holder_id=holder_id,
                month=month,
                year=year,
                holding_days_at_selection=holder.holding_days,
                balance_at_selection=holder.current_balance,
                reward_amount=reward_amount
            )
            session.add(winner)
            await session.flush()
            await session.refresh(winner)
            return winner
    
    async def get_winner(self, month: int, year: int) -> Optional[Winner]:
        """Get winner for specific month/year."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Winner)
                .options(selectinload(Winner.holder))
                .where(and_(Winner.month == month, Winner.year == year))
            )
            return result.scalar_one_or_none()
    
    async def get_recent_winners(self, limit: int = 10) -> List[Winner]:
        """Get recent winners."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Winner)
                .options(selectinload(Winner.holder))
                .order_by(desc(Winner.year), desc(Winner.month))
                .limit(limit)
            )
            return result.scalars().all()
    
    # Settings operations
    async def get_setting(self, key: str) -> Optional[str]:
        """Get bot setting value."""
        async with self.get_session() as session:
            result = await session.execute(
                select(BotSettings.value).where(BotSettings.key == key)
            )
            return result.scalar_one_or_none()
    
    async def set_setting(self, key: str, value: str, description: Optional[str] = None):
        """Set bot setting value."""
        async with self.get_session() as session:
            result = await session.execute(
                select(BotSettings).where(BotSettings.key == key)
            )
            setting = result.scalar_one_or_none()
            
            if setting:
                setting.value = value
                if description:
                    setting.description = description
            else:
                setting = BotSettings(
                    key=key,
                    value=value,
                    description=description
                )
                session.add(setting)


# Global database manager instance
_db_manager = None

async def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager
