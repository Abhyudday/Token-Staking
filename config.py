"""Configuration module for the Telegram rewards bot."""

import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration."""
    
    # Telegram Bot Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_USER_IDS: List[int] = [
        int(user_id.strip()) 
        for user_id in os.getenv("ADMIN_USER_IDS", "").split(",") 
        if user_id.strip().isdigit()
    ]
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Tatum API Configuration
    TATUM_API_KEY: str = os.getenv("TATUM_API_KEY", "")
    
    # Token Configuration
    TOKEN_CONTRACT_ADDRESS: str = os.getenv("TOKEN_CONTRACT_ADDRESS", "")
    BLOCKCHAIN_NETWORK: str = os.getenv("BLOCKCHAIN_NETWORK", "ethereum-sepolia")
    
    # Application Settings
    PORT: int = int(os.getenv("PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    STARTUP_DELAY: int = int(os.getenv("STARTUP_DELAY", "5"))  # Seconds to wait before health checks become strict
    
    # Holder Requirements
    MINIMUM_HOLD_DAYS: int = 30
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that all required configuration is present."""
        required_vars = [
            "BOT_TOKEN",
            "DATABASE_URL",
            "TATUM_API_KEY",
            "TOKEN_CONTRACT_ADDRESS"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True

# Create config instance
config = Config()
