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
        # DexScreener API for price (more reliable than Jupiter)
        self.dexscreener_url = "https://api.dexscreener.com/latest/dex/tokens"

    def get_token_holders(self, token_mint: str, page_limit: int = 1000, max_pages: int = 1000) -> List[Dict]:
        """Get all token accounts (holders) using Helius getTokenAccounts with pagination.
        Returns list of dicts with keys: owner, amount
        """
        holders: Dict[str, float] = {}
        page = 1
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
                    amount = float(amount_raw) if isinstance(amount_raw, (int, float)) else float(amount_raw or 0)
                    if not owner:
                        continue
                    holders[owner] = holders.get(owner, 0.0) + amount
                page += 1
            except Exception as e:
                logger.error(f"Helius get_token_holders error on page {page}: {e}")
                break
        # Transform to list of dicts to match previous interface
        return [{"owner": owner, "amount": amount} for owner, amount in holders.items()]

    def get_token_price_usd(self, token_mint: str) -> float:
        """Fetch token price in USD using multiple price sources for reliability."""
        price_sources = [
            ("DexScreener API", self._get_dexscreener_price),
            ("Birdeye API", self._get_birdeye_price),
            ("Raydium API", self._get_raydium_price),
            ("Helius Token Metadata", self._get_helius_price)
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
    
    def _get_dexscreener_price(self, token_mint: str) -> float:
        """Get price from DexScreener API"""
        try:
            # DexScreener API expects the token address directly in the URL
            dexscreener_url = f"{self.dexscreener_url}/{token_mint}"
            resp = requests.get(dexscreener_url, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                if data and "pairs" in data and data["pairs"]:
                    # Get the first pair (most liquid)
                    pair = data["pairs"][0]
                    price = pair.get("priceUsd")
                    if price is not None and price > 0:
                        logger.info(f"DexScreener: Found price ${price} for {token_mint}")
                        return float(price)
                    else:
                        logger.debug(f"DexScreener: No valid price in pair data")
                else:
                    logger.debug(f"DexScreener: No pairs found for token {token_mint}")
            else:
                logger.debug(f"DexScreener: HTTP {resp.status_code}")
        except Exception as e:
            logger.debug(f"DexScreener API error: {e}")
        return 0.0
    
    def _get_birdeye_price(self, token_mint: str) -> float:
        """Get price from Birdeye API"""
        try:
            birdeye_url = f"https://public-api.birdeye.so/public/price?address={token_mint}"
            resp = requests.get(birdeye_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data and data.get("success") and "data" in data:
                    price = data["data"].get("value")
                    if price is not None and price > 0:
                        return float(price)
        except Exception as e:
            logger.debug(f"Birdeye API error: {e}")
        return 0.0
    
    def _get_raydium_price(self, token_mint: str) -> float:
        """Get price from Raydium API"""
        try:
            raydium_url = f"https://api.raydium.io/v2/sdk/liquidity/mainnet/{token_mint}"
            resp = requests.get(raydium_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data and "price" in data:
                    price = data["price"]
                    if price is not None and price > 0:
                        return float(price)
        except Exception as e:
            logger.debug(f"Raydium API error: {e}")
        return 0.0
    
    def _get_helius_price(self, token_mint: str) -> float:
        """Get price from Helius token metadata"""
        try:
            helius_url = f"https://api.helius.xyz/v0/token-metadata?api-key={self.api_key}"
            resp = requests.post(helius_url, json={"mintAccounts": [token_mint]}, timeout=15)
            if resp.status_code == 200:
                arr = resp.json() or []
                if arr and isinstance(arr, list):
                    md = arr[0] or {}
                    price = md.get("price") or md.get("priceInfo", {}).get("price")
                    if price is not None and price > 0:
                        return float(price)
        except Exception as e:
            logger.debug(f"Helius API error: {e}")
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
