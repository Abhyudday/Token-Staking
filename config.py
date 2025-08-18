import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Database Configuration (Railway)
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # SOLSCAN Pro API Configuration
    SOLSCAN_API_KEY = os.getenv('SOLSCAN_API_KEY')
    
    # Token Configuration
    TOKEN_CONTRACT_ADDRESS = "9M7eYNNP4TdJCmMspKpdbEhvpdds6E5WFVTTLjXfVray"
    
    # Admin Configuration
    ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv('ADMIN_USER_IDS', '').split(',') if id.strip()]
    
    # Snapshot Configuration
    MINIMUM_USD_THRESHOLD = float(os.getenv('MINIMUM_USD_THRESHOLD', '0'))
    
    @classmethod
    def validate(cls):
        """Validate that all required environment variables are set"""
        required_vars = ['BOT_TOKEN', 'DATABASE_URL', 'SOLSCAN_API_KEY']
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True
