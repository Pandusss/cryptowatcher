"""
Service for working with coin cache (wrapper over CoinCacheManager)
"""
from typing import Dict, List, Optional
import logging

from app.core.redis_client import get_redis
from app.utils.cache import CoinCacheManager

logger = logging.getLogger("CoinCacheService")

class CoinCacheService:
    """
    Service for working with coin cache.
    Provides convenient interface for working with Redis cache.
    """
    
    def __init__(self):
        self.cache = CoinCacheManager()
    
    async def get_static(self, coin_id: str) -> Optional[Dict]:
        """
        Get static coin data from cache.
        """
        return await self.cache.get_static(coin_id)
    
    async def set_static(self, coin_id: str, static_data: Dict) -> bool:
        """
        Save static coin data to cache.
        """
        return await self.cache.set_static(coin_id, static_data)
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        """
        Get coin price from cache.
        """
        return await self.cache.get_price(coin_id)
    
    async def set_price(self, coin_id: str, price_data: Dict) -> bool:
        """
        Save coin price to cache.
        """
        return await self.cache.set_price(coin_id, price_data)
    
    async def get_static_and_prices_batch(
        self,
        coin_ids: List[str]
    ) -> Dict[str, Dict[str, Optional[Dict]]]:
        """
        Get static data and prices for multiple coins via Redis pipeline.
        
        Args:
            coin_ids: List of internal coin IDs
            
        Returns:
            Dictionary {coin_id: {"static": Optional[Dict], "price": Optional[Dict]}}
        """
        return await self.cache.get_static_and_prices_batch(coin_ids)
    
    async def get_image_url(self, coin_id: str) -> Optional[str]:
        """
        Get coin image URL from cache.
        """
        return await self.cache.get_image_url(coin_id)
    
    async def set_image_url(self, coin_id: str, image_url: str) -> bool:
        """
        Save coin image URL to cache.
        """
        return await self.cache.set_image_url(coin_id, image_url)
    
    async def get_chart(self, coin_id: str, period: str) -> Optional[List[Dict]]:
        """
        Get coin chart from cache.
        """
        return await self.cache.get_chart(coin_id, period)
    
    async def set_chart(self, coin_id: str, period: str, chart_data: List[Dict]) -> bool:
        """
        Save coin chart to cache.
        """
        return await self.cache.set_chart(coin_id, period, chart_data)
    
    async def clear_static_cache(self, coin_id: str) -> bool:
        """
        Clear static data cache for a coin.
        """
        redis = await get_redis()
        if not redis:
            return False
        
        try:
            static_key = self.cache._get_static_key(coin_id)
            image_key = self.cache._get_image_url_key(coin_id)
            await redis.delete(static_key, image_key)
            return True
        except Exception as e:
            return False
    
    async def clear_price_cache(self, coin_id: str) -> bool:
        """
        Clear price cache for a coin.
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
    
    async def clear_all_static_cache(self) -> bool:
        """
        Clear all static data cache.
        """
        redis = await get_redis()
        if not redis:
            return False
        
        try:
            keys_to_delete = []
            async for key in redis.scan_iter(match="coin_static:*"):
                keys_to_delete.append(key)
            
            if keys_to_delete:
                await redis.delete(*keys_to_delete)
            
            return True
        except Exception as e:
            logger.error(f"Error clearing static cache: {e}")
            return False