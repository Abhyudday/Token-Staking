import logging
import requests
from typing import List, Dict
from config import Config

logger = logging.getLogger(__name__)

class HeliusAPI:
    def __init__(self):
        self.api_key = Config.HELIUS_API_KEY
        # Helius RPC endpoint
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"
        # Jupiter API for price fallback
        self.jupiter_price_url = "https://price.jup.ag/v4/price"

    def get_token_holders(self, token_mint: str, page_limit: int = 1000, max_pages: int = 1000) -> List[Dict]:
        """Get all token accounts (holders) using Helius getTokenAccounts with pagination.
        Returns list of dicts with keys: owner, amount
        """
        holders: Dict[str, float] = {}
        page = 1
        
        # Get token decimals first
        token_decimals = self._get_token_decimals(token_mint)
        logger.info(f"Token {token_mint} has {token_decimals} decimals")
        
        while True:
            if page > max_pages:
                logger.warning("Reached max_pages limit while fetching token holders")
                break
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": "rewards-bot",
                    "method": "getTokenAccounts",
                    "params": {
                        "page": page,
                        "limit": page_limit,
                        "displayOptions": {},
                        "mint": token_mint,
                    },
                }
                resp = requests.post(self.rpc_url, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                result = (data or {}).get("result")
                token_accounts = (result or {}).get("token_accounts", [])
                if not token_accounts:
                    logger.info(f"No more token accounts after page {page}")
                    break
                logger.info(f"Helius: processing page {page} with {len(token_accounts)} accounts")
                for account in token_accounts:
                    owner = account.get("owner")
                    amount_raw = account.get("amount", 0)
                    
                    # Convert raw amount to actual token amount using decimals
                    if amount_raw and amount_raw > 0:
                        # Raw amount is in smallest units (e.g., lamports for SOL)
                        # Convert to actual tokens by dividing by 10^decimals
                        actual_amount = amount_raw / (10 ** token_decimals)
                        logger.debug(f"Wallet {owner[:8]}...{owner[-8:]}: raw={amount_raw}, decimals={token_decimals}, actual={actual_amount}")
                    else:
                        actual_amount = 0.0
                    
                    if not owner:
                        continue
                    holders[owner] = holders.get(owner, 0.0) + actual_amount
                page += 1
            except Exception as e:
                logger.error(f"Helius get_token_holders error on page {page}: {e}")
                break
        # Transform to list of dicts to match previous interface
        return [{"owner": owner, "amount": amount} for owner, amount in holders.items()]
    
    def _get_token_decimals(self, token_mint: str) -> int:
        """Get the number of decimals for a token"""
        try:
            # Try to get decimals from Helius token metadata
            helius_url = f"https://api.helius.xyz/v0/token-metadata?api-key={self.api_key}"
            resp = requests.post(helius_url, json={"mintAccounts": [token_mint]}, timeout=15)
            
            if resp.status_code == 200:
                arr = resp.json() or []
                if arr and isinstance(arr, list) and arr[0]:
                    metadata = arr[0]
                    decimals = metadata.get("decimals")
                    if decimals is not None:
                        logger.info(f"Token decimals from Helius: {decimals}")
                        return int(decimals)
            
            # Fallback: Use default Solana token decimals (usually 9)
            logger.warning(f"Could not determine token decimals, using default: 9")
            return 9
            
        except Exception as e:
            logger.error(f"Error getting token decimals: {e}")
            # Default fallback
            return 9

    def get_token_price_usd(self, token_mint: str) -> float:
        """Fetch token price in USD using multiple price sources for reliability."""
        price_sources = [
            ("Jupiter API", self._get_jupiter_price),
            ("DexScreener API", self._get_dexscreener_price),
            ("Birdeye API", self._get_birdeye_price),
            ("Helius Token Metadata", self._get_helius_price),
            ("Raydium API", self._get_raydium_price)
        ]
        
        for source_name, price_func in price_sources:
            try:
                price = price_func(token_mint)
                if price and price > 0:
                    logger.info(f"{source_name} returned price: ${price}")
                    return float(price)
                else:
                    logger.info(f"{source_name} returned no price or $0")
            except Exception as e:
                logger.warning(f"{source_name} failed: {e}")
                continue
        
        logger.warning(f"All price sources failed for token {token_mint}")
        return 0.0
    
    def _get_jupiter_price(self, token_mint: str) -> float:
        """Get price from Jupiter API"""
        try:
            jupiter_params = {"ids": token_mint}
            resp = requests.get(self.jupiter_price_url, params=jupiter_params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Jupiter API response: {data}")
                if data and "data" in data and token_mint in data["data"]:
                    price = data["data"][token_mint].get("price")
                    if price is not None and price > 0:
                        return float(price)
            else:
                logger.warning(f"Jupiter API returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.debug(f"Jupiter API error: {e}")
        return 0.0
    
    def _get_dexscreener_price(self, token_mint: str) -> float:
        """Get price from DexScreener API"""
        try:
            dexscreener_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
            resp = requests.get(dexscreener_url, timeout=15)
            
            logger.info(f"DexScreener API response status: {resp.status_code}")
            logger.info(f"DexScreener API response headers: {dict(resp.headers)}")
            
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"DexScreener API full response: {data}")
                
                if data and "pairs" in data and data["pairs"]:
                    # Get the first pair (usually the most liquid)
                    pair = data["pairs"][0]
                    logger.info(f"DexScreener first pair: {pair}")
                    
                    # Try to get price from different fields
                    price = None
                    if "priceUsd" in pair:
                        price = pair["priceUsd"]
                        logger.info(f"DexScreener priceUsd: {price}")
                    elif "price" in pair:
                        price = pair["price"]
                        logger.info(f"DexScreener price: {price}")
                    
                    if price is not None:
                        try:
                            price_float = float(price)
                            if price_float > 0:
                                logger.info(f"DexScreener API successful - price: ${price_float}")
                                return price_float
                            else:
                                logger.warning(f"DexScreener API returned zero or negative price: {price}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"DexScreener API price conversion failed: {price} -> {e}")
                else:
                    logger.warning(f"DexScreener API no pairs found in response")
            else:
                logger.warning(f"DexScreener API error status {resp.status_code}: {resp.text}")
                
        except Exception as e:
            logger.warning(f"DexScreener API exception: {e}")
        return 0.0
    
    def _get_birdeye_price(self, token_mint: str) -> float:
        """Get price from Birdeye API"""
        try:
            birdeye_url = f"https://public-api.birdeye.so/public/price?address={token_mint}"
            resp = requests.get(birdeye_url, timeout=15)
            
            logger.info(f"Birdeye API response status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Birdeye API full response: {data}")
                
                if data and data.get("success") and "data" in data:
                    price = data["data"].get("value")
                    logger.info(f"Birdeye API price value: {price}")
                    if price is not None and price > 0:
                        return float(price)
                else:
                    logger.warning(f"Birdeye API response structure: success={data.get('success')}, has_data={'data' in data}")
            else:
                logger.warning(f"Birdeye API error status {resp.status_code}: {resp.text}")
                
        except Exception as e:
            logger.warning(f"Birdeye API exception: {e}")
        return 0.0
    
    def _get_raydium_price(self, token_mint: str) -> float:
        """Get price from Raydium API"""
        try:
            raydium_url = f"https://api.raydium.io/v2/sdk/liquidity/mainnet/{token_mint}"
            resp = requests.get(raydium_url, timeout=15)
            
            logger.info(f"Raydium API response status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Raydium API full response: {data}")
                
                if data and "price" in data:
                    price = data["price"]
                    logger.info(f"Raydium API price: {price}")
                    if price is not None and price > 0:
                        return float(price)
                else:
                    logger.warning(f"Raydium API no price field found in response")
            else:
                logger.warning(f"Raydium API error status {resp.status_code}: {resp.text}")
                
        except Exception as e:
            logger.warning(f"Raydium API exception: {e}")
        return 0.0
    
    def _get_helius_price(self, token_mint: str) -> float:
        """Get price from Helius token metadata"""
        try:
            helius_url = f"https://api.helius.xyz/v0/token-metadata?api-key={self.api_key}"
            resp = requests.post(helius_url, json={"mintAccounts": [token_mint]}, timeout=15)
            
            logger.info(f"Helius API response status: {resp.status_code}")
            
            if resp.status_code == 200:
                arr = resp.json() or []
                logger.info(f"Helius API full response: {arr}")
                
                if arr and isinstance(arr, list):
                    md = arr[0] or {}
                    logger.info(f"Helius API metadata: {md}")
                    
                    price = md.get("price") or md.get("priceInfo", {}).get("price")
                    logger.info(f"Helius API price: {price}")
                    
                    if price is not None and price > 0:
                        return float(price)
                else:
                    logger.warning(f"Helius API no metadata found in response")
            else:
                logger.warning(f"Helius API error status {resp.status_code}: {resp.text}")
                
        except Exception as e:
            logger.warning(f"Helius API exception: {e}")
        return 0.0

    def validate_wallet_address(self, wallet_address: str) -> bool:
        try:
            if not wallet_address or len(wallet_address) < 32 or len(wallet_address) > 44:
                return False
            import base58
            try:
                base58.b58decode(wallet_address)
                return True
            except Exception:
                return False
        except Exception:
            return False
