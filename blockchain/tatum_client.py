"""Tatum API client for blockchain interactions."""

import httpx
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from config import config

logger = logging.getLogger(__name__)


class TatumClient:
    """Client for interacting with Tatum API."""
    
    def __init__(self):
        self.api_key = config.TATUM_API_KEY
        self.base_url = "https://api.tatum.io/v3"
        self.network = config.BLOCKCHAIN_NETWORK
        self.token_address = config.TOKEN_CONTRACT_ADDRESS
        
        # Configure HTTP client
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json"
            }
        )
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    def _get_network_prefix(self) -> str:
        """Get network prefix for API endpoints."""
        network_map = {
            "ethereum-mainnet": "ethereum",
            "ethereum-sepolia": "ethereum",
            "polygon-mainnet": "polygon",
            "bsc-mainnet": "bsc",
            "bsc-testnet": "bsc"
        }
        return network_map.get(self.network, "ethereum")
    
    async def get_token_balance(self, wallet_address: str) -> Optional[float]:
        """Get token balance for a wallet address."""
        try:
            network_prefix = self._get_network_prefix()
            url = f"{self.base_url}/{network_prefix}/account/balance/{wallet_address}"
            
            params = {
                "contractAddress": self.token_address
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, dict):
                if "balance" in data:
                    return float(data["balance"])
                elif "result" in data:
                    return float(data["result"]) / (10 ** 18)  # Convert from wei
            elif isinstance(data, list) and len(data) > 0:
                return float(data[0].get("balance", 0))
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting token balance for {wallet_address}: {e}")
            return None
    
    async def get_token_transactions(
        self, 
        wallet_address: str, 
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get token transactions for a wallet address."""
        try:
            network_prefix = self._get_network_prefix()
            url = f"{self.base_url}/{network_prefix}/account/transaction/{wallet_address}"
            
            params = {
                "contractAddress": self.token_address,
                "pageSize": 50
            }
            
            if from_block:
                params["from"] = from_block
            if to_block:
                params["to"] = to_block
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            transactions = []
            
            # Parse transactions based on response format
            if isinstance(data, list):
                for tx in data:
                    parsed_tx = self._parse_transaction(tx, wallet_address)
                    if parsed_tx:
                        transactions.append(parsed_tx)
            elif isinstance(data, dict) and "result" in data:
                for tx in data["result"]:
                    parsed_tx = self._parse_transaction(tx, wallet_address)
                    if parsed_tx:
                        transactions.append(parsed_tx)
            
            return transactions
            
        except Exception as e:
            logger.error(f"Error getting transactions for {wallet_address}: {e}")
            return []
    
    def _parse_transaction(self, tx_data: Dict[str, Any], wallet_address: str) -> Optional[Dict[str, Any]]:
        """Parse transaction data from Tatum API response."""
        try:
            # Determine transaction type (buy or sell)
            tx_type = "buy"
            amount = 0.0
            
            # Check if it's a token transfer
            if "tokenTransfers" in tx_data:
                for transfer in tx_data["tokenTransfers"]:
                    if transfer.get("contractAddress", "").lower() == self.token_address.lower():
                        amount = float(transfer.get("amount", 0)) / (10 ** 18)
                        
                        # Determine if it's a buy or sell based on direction
                        if transfer.get("to", "").lower() == wallet_address.lower():
                            tx_type = "buy"
                        elif transfer.get("from", "").lower() == wallet_address.lower():
                            tx_type = "sell"
                        break
            
            # Skip if no token transfer found
            if amount == 0:
                return None
            
            # Parse timestamp
            timestamp = None
            if "blockTime" in tx_data:
                timestamp = datetime.fromtimestamp(tx_data["blockTime"], tz=timezone.utc)
            elif "timeStamp" in tx_data:
                timestamp = datetime.fromtimestamp(int(tx_data["timeStamp"]), tz=timezone.utc)
            
            return {
                "hash": tx_data.get("hash", ""),
                "type": tx_type,
                "amount": amount,
                "block_number": int(tx_data.get("blockNumber", 0)),
                "timestamp": timestamp,
                "gas_fee": float(tx_data.get("gasUsed", 0)) * float(tx_data.get("gasPrice", 0)) / (10 ** 18),
                "from_address": tx_data.get("from", ""),
                "to_address": tx_data.get("to", "")
            }
            
        except Exception as e:
            logger.error(f"Error parsing transaction data: {e}")
            return None
    
    async def get_current_token_price(self) -> Optional[float]:
        """Get current token price in USD."""
        try:
            # This is a simplified implementation
            # You might need to use a different endpoint or service for price data
            network_prefix = self._get_network_prefix()
            url = f"{self.base_url}/{network_prefix}/erc20/price"
            
            params = {
                "contractAddress": self.token_address
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if isinstance(data, dict) and "price" in data:
                return float(data["price"])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting token price: {e}")
            return None
    
    async def validate_wallet_address(self, address: str) -> bool:
        """Validate if wallet address is valid."""
        try:
            # Basic validation for Ethereum-like addresses
            if not address.startswith("0x") or len(address) != 42:
                return False
            
            # Additional validation could be added here
            return True
            
        except Exception as e:
            logger.error(f"Error validating wallet address {address}: {e}")
            return False
    
    async def get_latest_block_number(self) -> Optional[int]:
        """Get the latest block number."""
        try:
            network_prefix = self._get_network_prefix()
            url = f"{self.base_url}/{network_prefix}/web3/{self.api_key}"
            
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if "result" in data:
                return int(data["result"], 16)  # Convert from hex
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest block number: {e}")
            return None
    
    async def monitor_token_holders(self, start_block: Optional[int] = None) -> List[Dict[str, Any]]:
        """Monitor for new token holders and transactions."""
        try:
            # Get recent transactions for the token contract
            network_prefix = self._get_network_prefix()
            url = f"{self.base_url}/{network_prefix}/transaction/address/{self.token_address}"
            
            params = {
                "pageSize": 50
            }
            
            if start_block:
                params["from"] = start_block
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            new_holders = []
            
            if isinstance(data, list):
                for tx in data:
                    if "tokenTransfers" in tx:
                        for transfer in tx["tokenTransfers"]:
                            if transfer.get("contractAddress", "").lower() == self.token_address.lower():
                                # Extract holder information
                                to_address = transfer.get("to", "")
                                amount = float(transfer.get("amount", 0)) / (10 ** 18)
                                
                                if to_address and amount > 0:
                                    new_holders.append({
                                        "wallet_address": to_address,
                                        "amount": amount,
                                        "transaction_hash": tx.get("hash", ""),
                                        "block_number": int(tx.get("blockNumber", 0)),
                                        "timestamp": datetime.fromtimestamp(
                                            tx.get("blockTime", 0), tz=timezone.utc
                                        ) if tx.get("blockTime") else None
                                    })
            
            return new_holders
            
        except Exception as e:
            logger.error(f"Error monitoring token holders: {e}")
            return []
