"""
Service for working with coin prices from Redis/WebSocket
"""
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional

from app.core.redis_client import get_redis
from app.utils.cache import CoinCacheManager
from app.utils.formatters import get_price_decimals

logger = logging.getLogger("CoinPriceService")

class CoinPriceService:
    """
    Service for working with coin prices.
    Gets prices ONLY from Redis cache (which is updated via Binance/OKX WebSocket).
    CoinGecko is NOT used for prices.
    """
    
    def __init__(self):
        self.cache = CoinCacheManager()
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        """
        Get current price for a coin.
        
        Args:
            coin_id: internal coin ID
            
        Returns:
            Dictionary with price data or None
        """
        cached_price = await self.cache.get_price(coin_id)
        if cached_price:
            return cached_price
        
        # If price is not in cache, return None (prices should come from WebSocket)
        return None
    
    async def get_prices_batch(self, coin_ids: List[str]) -> Dict[str, Optional[Dict]]:
        """
        Get prices for multiple coins.
        
        Args:
            coin_ids: list of internal coin IDs
            
        Returns:
            Dictionary {coin_id: price_data or None}
        """
        result = {}
        
        # Use Redis pipeline for batch reading
        redis = await get_redis()
        if not redis:
            return {coin_id: None for coin_id in coin_ids}
        
        try:
            async with redis.pipeline() as pipe:
                for coin_id in coin_ids:
                    pipe.get(self.cache._get_price_key(coin_id))
                
                results = await pipe.execute()
            
            for i, coin_id in enumerate(coin_ids):
                price_data = results[i]
                if price_data:
                    if isinstance(price_data, bytes):
                        price_data = price_data.decode('utf-8')
                    
                    try:
                        price_dict = json.loads(price_data) if price_data else None
                        result[coin_id] = price_dict
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.error(f"Price deserialization error for {coin_id}: {e}")
                        result[coin_id] = None
                else:
                    result[coin_id] = None
        
        except Exception as e:
            logger.error(f"Batch price reading error: {e}")
            result = {coin_id: None for coin_id in coin_ids}
        
        return result
    
    async def get_crypto_list_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Get prices for coin list ONLY from Redis (updated via Binance/OKX WebSocket).
        CoinGecko is NOT used for prices - only for static data (images, names).
        
        Args:
            coin_ids: list of internal coin IDs
            
        Returns:
            Dictionary {coin_id: price_data}
        """
        if not coin_ids:
            return {}
        
        logger.info(f"Loading prices for {len(coin_ids)} coins from Redis...")
        
        # Read prices ONLY from Redis cache
        prices_dict = {}
        redis = await get_redis()
        
        if redis:
            # Read all prices in parallel
            tasks = []
            for coin_id in coin_ids:
                tasks.append(self.cache.get_price(coin_id))
            
            cached_prices = await asyncio.gather(*tasks, return_exceptions=True)
            
            for coin_id, cached_price in zip(coin_ids, cached_prices):
                if isinstance(cached_price, Exception):
                    logger.error(f"Error reading price for {coin_id}: {cached_price}")
                    continue
                    
                if cached_price and cached_price.get("price", 0) > 0:
                    prices_dict[coin_id] = {
                        "price": cached_price.get("price", 0),
                        "percent_change_24h": cached_price.get("percent_change_24h", 0),
                        "volume_24h": cached_price.get("volume_24h", 0),
                        "priceDecimals": cached_price.get("priceDecimals", get_price_decimals(cached_price.get("price", 0))),
                    }
        else:
            logger.warning(f"Redis unavailable, prices not available")
            # Do NOT use CoinGecko as fallback - prices should only come from WebSocket
        
        logger.warning(f"Got prices: {len(prices_dict)} out of {len(coin_ids)} requested")
        return prices_dict
    
    async def refresh_price(self, coin_id: str) -> bool:
        """
        Force delete price from cache (to be updated via WebSocket).
        
        Args:
            coin_id: internal coin ID
            
        Returns:
            True if successful, False if error
        """
        redis = await get_redis()
        if not redis:
            return False
        
        try:
            price_key = self.cache._get_price_key(coin_id)
            await redis.delete(price_key)
            return True
        except Exception as e:
            return False
    
    async def set_price(self, coin_id: str, price_data: Dict) -> bool:
        """
        Set coin price in cache.
        Used by WebSocket handler for updating prices.
        
        Args:
            coin_id: internal coin ID
            price_data: dictionary with price data
            
        Returns:
            True if successful, False if error
        """
        return await self.cache.set_price(coin_id, price_data)
    
    async def get_prices_for_formatting(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Get prices for formatting in coin list.
        Simplified version of method for use in CoinService.
        
        Args:
            coin_ids: list of internal coin IDs
            
        Returns:
            Dictionary {coin_id: price_data}
            
        Note:
            If price not found, returns empty dictionary for that coin
        """
        prices = await self.get_prices_batch(coin_ids)
        result = {}
        for coin_id, price_dict in prices.items():
            if price_dict and price_dict.get("price", 0) > 0:
                result[coin_id] = {
                    "price": price_dict.get("price", 0),
                    "percent_change_24h": price_dict.get("percent_change_24h", 0),
                    "volume_24h": price_dict.get("volume_24h", 0),
                    "priceDecimals": price_dict.get("priceDecimals", get_price_decimals(price_dict.get("price", 0))),
                }
        return result