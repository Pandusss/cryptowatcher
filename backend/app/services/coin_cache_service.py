"""
Сервис для работы с кэшем монет (обертка над CoinCacheManager)
"""
from typing import Dict, List, Optional

from app.utils.cache import CoinCacheManager


class CoinCacheService:
    """
    Сервис для работы с кэшем монет.
    Предоставляет удобный интерфейс для работы с кэшем Redis.
    """
    
    def __init__(self):
        self.cache = CoinCacheManager()
    
    async def get_static(self, coin_id: str) -> Optional[Dict]:
        """
        Получить статические данные монеты из кэша.
        """
        return await self.cache.get_static(coin_id)
    
    async def set_static(self, coin_id: str, static_data: Dict) -> bool:
        """
        Сохранить статические данные монеты в кэш.
        """
        return await self.cache.set_static(coin_id, static_data)
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        """
        Получить цену монеты из кэша.
        """
        return await self.cache.get_price(coin_id)
    
    async def set_price(self, coin_id: str, price_data: Dict) -> bool:
        """
        Сохранить цену монеты в кэш.
        """
        return await self.cache.set_price(coin_id, price_data)
    
    async def get_static_and_prices_batch(
        self, 
        coin_ids: List[str]
    ) -> Dict[str, Dict[str, Optional[Dict]]]:
        """
        Получить статику и цены для нескольких монет через Redis pipeline.
        
        Args:
            coin_ids: Список внутренних ID монет
            
        Returns:
            Словарь {coin_id: {"static": Optional[Dict], "price": Optional[Dict]}}
        """
        return await self.cache.get_static_and_prices_batch(coin_ids)
    
    async def get_image_url(self, coin_id: str) -> Optional[str]:
        """
        Получить URL изображения монеты из кэша.
        """
        return await self.cache.get_image_url(coin_id)
    
    async def set_image_url(self, coin_id: str, image_url: str) -> bool:
        """
        Сохранить URL изображения монеты в кэш.
        """
        return await self.cache.set_image_url(coin_id, image_url)
    
    async def get_chart(self, coin_id: str, period: str) -> Optional[List[Dict]]:
        """
        Получить график монеты из кэша.
        """
        return await self.cache.get_chart(coin_id, period)
    
    async def set_chart(self, coin_id: str, period: str, chart_data: List[Dict]) -> bool:
        """
        Сохранить график монеты в кэш.
        """
        return await self.cache.set_chart(coin_id, period, chart_data)
    
    async def clear_static_cache(self, coin_id: str) -> bool:
        """
        Очистить кэш статических данных для монеты.
        """
        redis = await self.cache._get_redis()
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
        Очистить кэш цены для монеты.
        """
        redis = await self.cache._get_redis()
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
        Очистить весь кэш статических данных.
        """
        redis = await self.cache._get_redis()
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
            print(f"[CoinCacheService] Ошибка при очистке кэша статики: {e}")
            return False