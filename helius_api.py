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
        # Helius REST token api for price (fallback to Jupiter/Coingecko if needed)
        self.token_price_url = f"https://api.helius.xyz/v0/token-metadata?api-key={self.api_key}"

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
        """Fetch token price in USD using Helius token metadata endpoint if price available.
        If not available, return 0 and caller can decide how to proceed.
        """
        try:
            # Helius token metadata endpoint can return price info for common tokens
            resp = requests.post(self.token_price_url, json={"mintAccounts": [token_mint] }, timeout=15)
            if resp.status_code == 200:
                arr = resp.json() or []
                if arr and isinstance(arr, list):
                    md = arr[0] or {}
                    price = md.get("price") or md.get("priceInfo", {}).get("price")
                    if price is not None:
                        return float(price)
            logger.warning("Token price not available from Helius; defaulting to 0")
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching token price from Helius: {e}")
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
