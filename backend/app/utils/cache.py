"""
Cache utilities
"""
import json
import logging
from typing import Dict, List, Optional

from app.core.redis_client import get_redis

logger = logging.getLogger(f"UtilsCache")

class CoinCacheManager:
    
    # TTL for different data types
    CACHE_TTL_COIN_STATIC = 3600  # 1 hour for static data
    CACHE_TTL_COIN_PRICE = 10  # 10 seconds for prices
    CACHE_TTL_IMAGE_URL = 604800  # 7 days for icons
    CACHE_TTL_CHART = 60  # 1 minute for charts
    
    @staticmethod
    def _get_static_key(coin_id: str) -> str:
        return f"coin_static:{coin_id}"
    
    @staticmethod
    def _get_price_key(coin_id: str) -> str:
        return f"coin_price:{coin_id}"
    
    @staticmethod
    def _get_chart_key(coin_id: str, period: str) -> str:
        return f"coin_chart:{coin_id}:{period}"
    
    @staticmethod
    def _get_image_url_key(coin_id: str) -> str:
        return f"coin_image_url:{coin_id}"
    
    async def get_static(self, coin_id: str) -> Optional[Dict]:
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            data = await redis.get(self._get_static_key(coin_id))
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Static reading error for {coin_id}: {e}")
            return None
    
    async def set_static(self, coin_id: str, static_data: Dict) -> bool:
        redis = await get_redis()
        if not redis:
            return False
        
        try:
            await redis.setex(
                self._get_static_key(coin_id),
                self.CACHE_TTL_COIN_STATIC,
                json.dumps(static_data)
            )
            return True
        except Exception as e:
            logger.error(f"Static recording error for {coin_id}: {e}")
            return False
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            data = await redis.get(self._get_price_key(coin_id))
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Error reading the price for {coin_id}: {e}")
            return None
    
    async def set_price(self, coin_id: str, price_data: Dict) -> bool:
        redis = await get_redis()
        if not redis:
            return False
        
        try:
            await redis.setex(
                self._get_price_key(coin_id),
                self.CACHE_TTL_COIN_PRICE,
                json.dumps(price_data)
            )
            return True
        except Exception as e:
            logger.error(f"Error recording the price for {coin_id}: {e}")
            return False
    
    async def get_chart(self, coin_id: str, period: str) -> Optional[List[Dict]]:
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            data = await redis.get(self._get_chart_key(coin_id, period))
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Chart reading error for {coin_id}: {e}")
            return None
    
    async def set_chart(self, coin_id: str, period: str, chart_data: List[Dict]) -> bool:
        redis = await get_redis()
        if not redis:
            return False
        
        try:
            await redis.setex(
                self._get_chart_key(coin_id, period),
                self.CACHE_TTL_CHART,
                json.dumps(chart_data)
            )
            return True
        except Exception as e:
            logger.error(f"Chart recording error for {coin_id}: {e}")
            return False
    
    async def get_image_url(self, coin_id: str) -> Optional[str]:
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            return await redis.get(self._get_image_url_key(coin_id))
        except Exception as e:
            logger.error(f"Error reading the URL for {coin_id}: {e}")
            return None
    
    async def set_image_url(self, coin_id: str, image_url: str) -> bool:
        redis = await get_redis()
        if not redis:
            return False
        
        try:
            await redis.setex(
                self._get_image_url_key(coin_id),
                self.CACHE_TTL_IMAGE_URL,
                image_url
            )
            return True
        except Exception as e:
            logger.error(f"Error writing the URL for {coin_id}: {e}")
            return False
    
    async def get_static_and_prices_batch(
        self, 
        coin_ids: List[str]
    ) -> Dict[str, Dict[str, Optional[Dict]]]:
        """
        Get statics and prices for multiple coins via Redis pipeline
        
        Args:
            coin_ids: List of internal Coin IDs
            
        Returns:
            Dictionary {coin_id: {"static": Optional[Dict], "price": Optional[Dict]}}
        """
        redis = await get_redis()
        if not redis:
            return {coin_id: {"static": None, "price": None} for coin_id in coin_ids}
        
        result = {}
        
        try:
            # Using pipeline for batch requests
            async with redis.pipeline() as pipe:
                # Add all requests to the pipeline
                for coin_id in coin_ids:
                    pipe.get(self._get_static_key(coin_id))
                    pipe.get(self._get_price_key(coin_id))
                
                # Execute all requests in one round-trip
                results = await pipe.execute()
            
            # Parse results
            # results[0] - static for coin_ids[0]
            # results[1] - price for coin_ids[0]
            # results[2] - static for coin_ids[1]
            # results[3] - price for coin_ids[1]
            # and so on
            for i, coin_id in enumerate(coin_ids):
                static_idx = i * 2
                price_idx = i * 2 + 1
                
                static_data = results[static_idx]
                price_data = results[price_idx]
                
                # Deserialize JSON
                static_dict = None
                if static_data:
                    try:
                        if isinstance(static_data, bytes):
                            static_data = static_data.decode('utf-8')
                        static_dict = json.loads(static_data) if static_data else None
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.error(f"Static deserialization error for {coin_id}: {e}")
                
                price_dict = None
                if price_data:
                    try:
                        if isinstance(price_data, bytes):
                            price_data = price_data.decode('utf-8')
                        price_dict = json.loads(price_data) if price_data else None
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.error(f"Price deserialization error for {coin_id}: {e}")
                
                result[coin_id] = {
                    "static": static_dict,
                    "price": price_dict
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Batch cache read error: {e}")
            # In case of error, return None for all coins
            return {coin_id: {"static": None, "price": None} for coin_id in coin_ids}