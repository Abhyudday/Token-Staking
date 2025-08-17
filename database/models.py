"""Database models for the rewards bot."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Holder(Base):
    """Model for token holders."""
    
    __tablename__ = "holders"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String(42), unique=True, index=True, nullable=False)
    telegram_user_id = Column(Integer, unique=True, index=True, nullable=True)
    telegram_username = Column(String(255), nullable=True)
    first_buy_date = Column(DateTime(timezone=True), nullable=False)
    last_activity_date = Column(DateTime(timezone=True), nullable=False)
    current_balance = Column(Numeric(precision=36, scale=18), nullable=False, default=0)
    total_bought = Column(Numeric(precision=36, scale=18), nullable=False, default=0)
    total_sold = Column(Numeric(precision=36, scale=18), nullable=False, default=0)
    is_eligible = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transactions = relationship("Transaction", back_populates="holder", cascade="all, delete-orphan")
    winners = relationship("Winner", back_populates="holder")
    
    @property
    def holding_days(self) -> int:
        """Calculate how many days the holder has been holding."""
        now = datetime.now(timezone.utc)
        return (now - self.first_buy_date).days
    
    @property
    def is_eligible_for_reward(self) -> bool:
        """Check if holder is eligible for monthly reward."""
        from config import config
        return (
            self.is_eligible and 
            self.holding_days >= config.MINIMUM_HOLD_DAYS and 
            self.current_balance > 0
        )
    
    def __repr__(self):
        return f"<Holder(wallet={self.wallet_address[:8]}..., balance={self.current_balance})>"


class Transaction(Base):
    """Model for tracking buy/sell transactions."""
    
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    holder_id = Column(Integer, ForeignKey("holders.id"), nullable=False, index=True)
    transaction_hash = Column(String(66), unique=True, nullable=False, index=True)
    transaction_type = Column(String(10), nullable=False)  # 'buy' or 'sell'
    amount = Column(Numeric(precision=36, scale=18), nullable=False)
    price_usd = Column(Numeric(precision=10, scale=2), nullable=True)
    gas_fee = Column(Numeric(precision=36, scale=18), nullable=True)
    block_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    holder = relationship("Holder", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(type={self.transaction_type}, amount={self.amount}, hash={self.transaction_hash[:8]}...)>"


class Winner(Base):
    """Model for monthly winners."""
    
    __tablename__ = "winners"
    
    id = Column(Integer, primary_key=True, index=True)
    holder_id = Column(Integer, ForeignKey("holders.id"), nullable=False, index=True)
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)
    holding_days_at_selection = Column(Integer, nullable=False)
    balance_at_selection = Column(Numeric(precision=36, scale=18), nullable=False)
    reward_amount = Column(String(100), nullable=True)  # Flexible for different reward types
    reward_sent = Column(Boolean, default=False, nullable=False)
    announcement_message_id = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    selected_at = Column(DateTime(timezone=True), server_default=func.now())
    reward_sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    holder = relationship("Holder", back_populates="winners")
    
    @property
    def period_display(self) -> str:
        """Get display string for the winning period."""
        from datetime import datetime
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        return f"{month_names[self.month - 1]} {self.year}"
    
    def __repr__(self):
        return f"<Winner(holder_id={self.holder_id}, period={self.month}/{self.year})>"


class BotSettings(Base):
    """Model for bot configuration and settings."""
    
    __tablename__ = "bot_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<BotSettings(key={self.key}, value={self.value})>"
