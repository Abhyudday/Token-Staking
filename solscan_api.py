import requests
import logging
from config import Config
from datetime import datetime

logger = logging.getLogger(__name__)

class SolscanAPI:
    def __init__(self):
        self.api_key = Config.SOLSCAN_API_KEY
        self.base_url = "https://public-api.solscan.io"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
    
    def get_token_holders(self, token_address, limit=1000):
        """Get token holders from SOLSCAN Pro API"""
        try:
            url = f"{self.base_url}/token/holders"
            params = {
                "tokenAddress": token_address,
                "limit": limit,
                "offset": 0
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success"):
                return data.get("data", [])
            else:
                logger.error(f"SOLSCAN API error: {data.get('message', 'Unknown error')}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching token holders: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching token holders: {e}")
            return []
    
    def get_token_price(self, token_address):
        """Get current token price in USD"""
        try:
            url = f"{self.base_url}/market/token/{token_address}"
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success"):
                price_data = data.get("data", {})
                return float(price_data.get("priceUsdt", 0))
            else:
                logger.error(f"SOLSCAN API error getting price: {data.get('message', 'Unknown error')}")
                return 0
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching token price: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error fetching token price: {e}")
            return 0
    
    def get_token_info(self, token_address):
        """Get basic token information"""
        try:
            url = f"{self.base_url}/token/meta"
            params = {"tokenAddress": token_address}
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success"):
                return data.get("data", {})
            else:
                logger.error(f"SOLSCAN API error getting token info: {data.get('message', 'Unknown error')}")
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching token info: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching token info: {e}")
            return {}
    
    def get_holder_transactions(self, wallet_address, token_address, limit=100):
        """Get recent transactions for a specific holder and token"""
        try:
            url = f"{self.base_url}/account/transactions"
            params = {
                "account": wallet_address,
                "limit": limit
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success"):
                transactions = data.get("data", [])
                # Filter transactions related to the specific token
                token_transactions = [
                    tx for tx in transactions 
                    if token_address in str(tx.get("tokenTransfers", []))
                ]
                return token_transactions
            else:
                logger.error(f"SOLSCAN API error getting transactions: {data.get('message', 'Unknown error')}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching transactions: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching transactions: {e}")
            return []
    
    def validate_wallet_address(self, wallet_address):
        """Validate if a wallet address is a valid Solana address"""
        try:
            # Basic Solana address validation (44 characters, base58)
            if len(wallet_address) != 44:
                return False
            
            # Check if it's a valid base58 string
            import base58
            try:
                base58.b58decode(wallet_address)
                return True
            except:
                return False
                
        except Exception as e:
            logger.error(f"Error validating wallet address: {e}")
            return False
