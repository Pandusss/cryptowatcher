"""
CoinGecko Price Provider

Price provider from CoinGecko REST API (via HTTP requests).
Fetches prices via batch requests and caches them in Redis.
"""
import logging
from typing import Dict, List, Optional

from app.providers.base_adapters import BasePriceAdapter
from app.providers.coingecko_client import CoinGeckoClient
from app.core.coin_registry import coin_registry
from app.utils.cache import CoinCacheManager
from app.utils.formatters import get_price_decimals

logger = logging.getLogger("CoinGeckoPrice")


class CoinGeckoPriceAdapter(BasePriceAdapter):
    """Price adapter for CoinGecko REST API"""
    
    def __init__(self):
        self.client = CoinGeckoClient()
        self.cache = CoinCacheManager()
    
    def _get_tracked_coins(self) -> List[Dict]:
        """
        Get list of coins that should be tracked via CoinGecko:
        - Must have 'coingecko' in external_ids
        - Must have 'coingecko' in price_priority
        """
        tracked = []
        all_coins = coin_registry.get_all_coins(enabled_only=True)
        
        for coin in all_coins:
            # Check if coin has coingecko ID
            coingecko_id = coin.external_ids.get("coingecko")
            if not coingecko_id:
                continue
            
            # Check if coingecko is in price_priority
            if "coingecko" not in coin.price_priority:
                continue
            
            tracked.append({
                "internal_id": coin.id,
                "coingecko_id": coingecko_id
            })
        
        return tracked
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        """
        Get price for a single coin
        
        Args:
            coin_id: External CoinGecko ID (e.g., "bitcoin")
            
        Returns:
            Dictionary with price data or None
        """
        # Find internal coin ID
        coin = coin_registry.find_coin_by_external_id("coingecko", coin_id)
        if not coin:
            return None
        
        internal_id = coin.id
        
        # Check if coingecko is in price_priority
        if "coingecko" not in coin.price_priority:
            return None
        
        # Try to get from cache first
        cached_price = await self.cache.get_price(internal_id)
        if cached_price:
            return cached_price
        
        # Fetch from API
        try:
            response = await self.client.get(
                "/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_24hr_vol": "true"
                }
            )
            
            if coin_id not in response:
                return None
            
            coin_data = response[coin_id]
            
            # Extract data
            price = coin_data.get("usd", 0)
            if price <= 0:
                return None
            
            price_change_24h = coin_data.get("usd_24h_change", 0)
            volume_24h = coin_data.get("usd_24h_vol", 0)
            
            # Format price data
            price_data = {
                "price": float(price),
                "percent_change_24h": float(price_change_24h),
                "volume_24h": float(volume_24h),
                "priceDecimals": get_price_decimals(price),
            }
            
            # Cache it
            await self.cache.set_price(internal_id, price_data)
            
            return price_data
            
        except Exception as e:
            logger.error(f"Error fetching price for {coin_id}: {e}")
            return None
    
    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Get prices for multiple coins via batch request
        
        Args:
            coin_ids: List of external CoinGecko IDs
            
        Returns:
            Dictionary {coin_id: {price, percent_change_24h, volume_24h}}
        """
        if not coin_ids:
            return {}
        
        result = {}
        
        # Filter coins: only those with coingecko in price_priority
        filtered_ids = []
        coin_id_map = {}  # coingecko_id -> internal_id
        
        for coingecko_id in coin_ids:
            coin = coin_registry.find_coin_by_external_id("coingecko", coingecko_id)
            if not coin:
                continue
            
            # Check if coingecko is in price_priority
            if "coingecko" not in coin.price_priority:
                continue
            
            filtered_ids.append(coingecko_id)
            coin_id_map[coingecko_id] = coin.id
        
        if not filtered_ids:
            return {}
        
        # Check cache first
        cached_prices = {}
        ids_to_fetch = []
        
        for coingecko_id in filtered_ids:
            internal_id = coin_id_map[coingecko_id]
            cached = await self.cache.get_price(internal_id)
            if cached:
                cached_prices[coingecko_id] = cached
            else:
                ids_to_fetch.append(coingecko_id)
        
        # Fetch missing prices from API
        if ids_to_fetch:
            try:
                # Batch request (max 250 coins per request according to docs)
                batch_size = 250
                for i in range(0, len(ids_to_fetch), batch_size):
                    batch = ids_to_fetch[i:i + batch_size]
                    ids_param = ",".join(batch)
                    
                    response = await self.client.get(
                        "/simple/price",
                        params={
                            "ids": ids_param,
                            "vs_currencies": "usd",
                            "include_24hr_change": "true",
                            "include_24hr_vol": "true"
                        }
                    )
                    
                    # Process response
                    for coingecko_id in batch:
                        if coingecko_id not in response:
                            continue
                        
                        coin_data = response[coingecko_id]
                        internal_id = coin_id_map[coingecko_id]
                        
                        price = coin_data.get("usd", 0)
                        if price <= 0:
                            continue
                        
                        price_change_24h = coin_data.get("usd_24h_change", 0)
                        volume_24h = coin_data.get("usd_24h_vol", 0)
                        
                        price_data = {
                            "price": float(price),
                            "percent_change_24h": float(price_change_24h),
                            "volume_24h": float(volume_24h),
                            "priceDecimals": get_price_decimals(price),
                        }
                        
                        # Cache it
                        await self.cache.set_price(internal_id, price_data)
                        
                        # Add to result
                        cached_prices[coingecko_id] = price_data
                        
            except Exception as e:
                logger.error(f"Error fetching batch prices: {e}")
        
        # Return all prices (cached + fetched)
        return cached_prices
    
    def is_available(self, coin_id: str) -> bool:
        """
        Check if coin is available on CoinGecko
        
        Args:
            coin_id: External CoinGecko ID
            
        Returns:
            True if available and coingecko is in price_priority
        """
        coin = coin_registry.find_coin_by_external_id("coingecko", coin_id)
        if not coin:
            return False
        
        # Check if coingecko is in price_priority
        return "coingecko" in coin.price_priority
    
    async def close(self):
        """Close HTTP client"""
        await self.client.close()


# Global instance
coingecko_price_adapter = CoinGeckoPriceAdapter()

