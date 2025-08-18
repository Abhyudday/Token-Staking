"""Bitquery API client for blockchain interactions."""

import httpx
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from config import config

logger = logging.getLogger(__name__)


class BitqueryClient:
    """Client for interacting with Bitquery API."""
    
    def __init__(self):
        self.api_key = config.BITQUERY_API_KEY if hasattr(config, 'BITQUERY_API_KEY') else config.TATUM_API_KEY
        self.base_url = "https://graphql.bitquery.io"
        self.network = self._get_bitquery_network()
        self.token_address = config.TOKEN_CONTRACT_ADDRESS
        
        # Configure HTTP client
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }
        )
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    def _get_bitquery_network(self) -> str:
        """Get Bitquery network identifier."""
        network_map = {
            "ethereum-mainnet": "ethereum",
            "ethereum-sepolia": "ethereum",
            "polygon-mainnet": "matic",
            "bsc-mainnet": "bsc",
            "bsc-testnet": "bsc",
            "solana-mainnet": "solana",
            "solana-devnet": "solana",
            "solana-testnet": "solana"
        }
        return network_map.get(config.BLOCKCHAIN_NETWORK, "ethereum")
    
    def _is_solana_network(self) -> bool:
        """Check if the current network is Solana."""
        return config.BLOCKCHAIN_NETWORK.startswith("solana")
    
    async def get_token_holders_with_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get token holders with their holding history for leaderboard."""
        try:
            if self._is_solana_network():
                # Use Solana-specific query
                query = """
                query GetSolanaTokenHolders($tokenAddress: String!, $limit: Int!) {
                  Solana {
                    TokenHolders(
                      where: {BalanceUpdate: {Currency: {MintAddress: {is: $tokenAddress}}}}
                      orderBy: {descending: Balance_Amount}
                      limit: {count: $limit}
                    ) {
                      Holder {
                        Address
                      }
                      Balance {
                        Amount
                      }
                      BalanceUpdate {
                        FirstDate
                        LastDate
                        transactions: Count
                        InAmount
                        OutAmount
                      }
                    }
                  }
                }
                """
                variables = {
                    "tokenAddress": self.token_address,
                    "limit": limit
                }
            else:
                # Use EVM-specific query
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                query = """
                query GetTokenHolders($tokenAddress: String!, $date: String!, $limit: Int!) {
                  EVM(dataset: archive, network: eth) {
                    TokenHolders(
                      date: $date
                      tokenSmartContract: $tokenAddress
                      limit: {count: $limit}
                      orderBy: {descending: Balance_Amount}
                      where: {Balance: {Amount: {gt: "0"}}}
                    ) {
                      Holder {
                        Address
                      }
                      Balance {
                        Amount
                      }
                      BalanceUpdate {
                        FirstDate
                        LastDate
                        transactions: Count
                        InAmount
                        OutAmount
                      }
                    }
                  }
                }
                """
                variables = {
                    "tokenAddress": self.token_address,
                    "date": today,
                    "limit": limit
                }
            
            response = await self.client.post(
                self.base_url,
                json={"query": query, "variables": variables}
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                logger.error(f"Bitquery API errors: {data['errors']}")
                return []
            
            # Parse response based on network
            holders = []
            if self._is_solana_network():
                token_holders = data.get("data", {}).get("Solana", {}).get("TokenHolders", [])
            else:
                token_holders = data.get("data", {}).get("EVM", {}).get("TokenHolders", [])
            
            for holder_data in token_holders:
                holder = self._parse_holder_data(holder_data)
                if holder:
                    holders.append(holder)
            
            return holders
            
        except Exception as e:
            logger.error(f"Error getting token holders from Bitquery: {e}")
            return []
    
    def _parse_holder_data(self, holder_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse holder data from Bitquery response."""
        try:
            holder_info = holder_data.get("Holder", {})
            balance_info = holder_data.get("Balance", {})
            balance_update = holder_data.get("BalanceUpdate", {})
            
            wallet_address = holder_info.get("Address", "")
            balance = float(balance_info.get("Amount", 0))
            
            # Parse dates
            first_date_str = balance_update.get("FirstDate")
            last_date_str = balance_update.get("LastDate")
            
            first_date = None
            last_date = None
            
            if first_date_str:
                try:
                    first_date = datetime.fromisoformat(first_date_str.replace("Z", "+00:00"))
                except:
                    # Try parsing as date only
                    first_date = datetime.strptime(first_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            
            if last_date_str:
                try:
                    last_date = datetime.fromisoformat(last_date_str.replace("Z", "+00:00"))
                except:
                    # Try parsing as date only
                    last_date = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            
            # Calculate holding days
            holding_days = 0
            if first_date:
                if last_date:
                    # If they've made recent transactions, use last transaction date
                    end_date = max(last_date, first_date)
                else:
                    # If no recent transactions, use current date
                    end_date = datetime.now(timezone.utc)
                
                holding_days = (end_date - first_date).days
            
            # Get transaction metrics
            transaction_count = balance_update.get("transactions", 0)
            in_amount = float(balance_update.get("InAmount", 0))
            out_amount = float(balance_update.get("OutAmount", 0))
            
            # Determine if holder is eligible (hasn't sold all tokens)
            is_eligible = balance > 0 and (out_amount == 0 or in_amount > out_amount)
            
            return {
                "wallet_address": wallet_address,
                "current_balance": balance,
                "holding_days": holding_days,
                "first_buy_date": first_date,
                "last_activity_date": last_date,
                "transaction_count": transaction_count,
                "total_bought": in_amount,
                "total_sold": out_amount,
                "is_eligible": is_eligible
            }
            
        except Exception as e:
            logger.error(f"Error parsing holder data: {e}")
            return None
    
    async def get_token_balance(self, wallet_address: str) -> Optional[float]:
        """Get current token balance for a wallet address."""
        try:
            if self._is_solana_network():
                # Solana token balance query
                query = """
                query GetSolanaBalance($walletAddress: String!, $tokenAddress: String!) {
                  Solana {
                    TokenHolders(
                      where: {
                        Holder: {Address: {is: $walletAddress}}
                        BalanceUpdate: {Currency: {MintAddress: {is: $tokenAddress}}}
                      }
                    ) {
                      Balance {
                        Amount
                      }
                    }
                  }
                }
                """
                variables = {
                    "walletAddress": wallet_address,
                    "tokenAddress": self.token_address
                }
            else:
                # EVM token balance query
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                query = """
                query GetTokenBalance($walletAddress: String!, $tokenAddress: String!, $date: String!) {
                  EVM(dataset: archive, network: eth) {
                    TokenHolders(
                      date: $date
                      tokenSmartContract: $tokenAddress
                      where: {
                        Holder: {Address: {is: $walletAddress}}
                      }
                    ) {
                      Balance {
                        Amount
                      }
                    }
                  }
                }
                """
                variables = {
                    "walletAddress": wallet_address,
                    "tokenAddress": self.token_address,
                    "date": today
                }
            
            response = await self.client.post(
                self.base_url,
                json={"query": query, "variables": variables}
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                logger.error(f"Bitquery API errors: {data['errors']}")
                return None
            
            # Parse response
            if self._is_solana_network():
                holders = data.get("data", {}).get("Solana", {}).get("TokenHolders", [])
            else:
                holders = data.get("data", {}).get("EVM", {}).get("TokenHolders", [])
            
            if holders and len(holders) > 0:
                return float(holders[0].get("Balance", {}).get("Amount", 0))
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting token balance for {wallet_address}: {e}")
            return None
    
    async def get_holder_details(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific holder."""
        try:
            if self._is_solana_network():
                query = """
                query GetSolanaHolderDetails($walletAddress: String!, $tokenAddress: String!) {
                  Solana {
                    TokenHolders(
                      where: {
                        Holder: {Address: {is: $walletAddress}}
                        BalanceUpdate: {Currency: {MintAddress: {is: $tokenAddress}}}
                      }
                    ) {
                      Holder {
                        Address
                      }
                      Balance {
                        Amount
                      }
                      BalanceUpdate {
                        FirstDate
                        LastDate
                        transactions: Count
                        InAmount
                        OutAmount
                      }
                    }
                  }
                }
                """
                variables = {
                    "walletAddress": wallet_address,
                    "tokenAddress": self.token_address
                }
            else:
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                query = """
                query GetHolderDetails($walletAddress: String!, $tokenAddress: String!, $date: String!) {
                  EVM(dataset: archive, network: eth) {
                    TokenHolders(
                      date: $date
                      tokenSmartContract: $tokenAddress
                      where: {
                        Holder: {Address: {is: $walletAddress}}
                      }
                    ) {
                      Holder {
                        Address
                      }
                      Balance {
                        Amount
                      }
                      BalanceUpdate {
                        FirstDate
                        LastDate
                        transactions: Count
                        InAmount
                        OutAmount
                      }
                    }
                  }
                }
                """
                variables = {
                    "walletAddress": wallet_address,
                    "tokenAddress": self.token_address,
                    "date": today
                }
            
            response = await self.client.post(
                self.base_url,
                json={"query": query, "variables": variables}
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                logger.error(f"Bitquery API errors: {data['errors']}")
                return None
            
            # Parse response
            if self._is_solana_network():
                holders = data.get("data", {}).get("Solana", {}).get("TokenHolders", [])
            else:
                holders = data.get("data", {}).get("EVM", {}).get("TokenHolders", [])
            
            if holders and len(holders) > 0:
                return self._parse_holder_data(holders[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting holder details for {wallet_address}: {e}")
            return None
