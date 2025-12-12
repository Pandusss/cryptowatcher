"""
Утилиты для работы с кэшем
"""
import json
from typing import Dict, List, Optional

from app.core.redis_client import get_redis


class CoinCacheManager:
    
    # TTL для разных типов данных
    CACHE_TTL_TOP3000 = 3600  # 1 час для топ-3000
    CACHE_TTL_COIN_STATIC = 3600  # 1 час для статических данных
    CACHE_TTL_COIN_PRICE = 10  # 10 секунд для цен
    CACHE_TTL_IMAGE_URL = 604800  # 7 дней для иконок
    CACHE_TTL_PRICE_DECIMALS = 86400  # 1 день для decimals
    CACHE_TTL_CHART = 60  # 1 минута для графиков
    
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
            print(f"[CoinCacheManager] Ошибка чтения статики для {coin_id}: {e}")
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
            print(f"[CoinCacheManager] Ошибка записи статики для {coin_id}: {e}")
            return False
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            data = await redis.get(self._get_price_key(coin_id))
            return json.loads(data) if data else None
        except Exception as e:
            print(f"[CoinCacheManager] Ошибка чтения цены для {coin_id}: {e}")
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
            print(f"[CoinCacheManager] Ошибка записи цены для {coin_id}: {e}")
            return False
    
    async def get_chart(self, coin_id: str, period: str) -> Optional[List[Dict]]:
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            data = await redis.get(self._get_chart_key(coin_id, period))
            return json.loads(data) if data else None
        except Exception as e:
            print(f"[CoinCacheManager] Ошибка чтения графика для {coin_id}: {e}")
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
            print(f"[CoinCacheManager] Ошибка записи графика для {coin_id}: {e}")
            return False
    
    async def get_image_url(self, coin_id: str) -> Optional[str]:
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            return await redis.get(self._get_image_url_key(coin_id))
        except Exception as e:
            print(f"[CoinCacheManager] Ошибка чтения URL для {coin_id}: {e}")
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
            print(f"[CoinCacheManager] Ошибка записи URL для {coin_id}: {e}")
            return False

