"""
OKX Price Provider

Провайдер цен из OKX WebSocket (через Redis кэш).
WebSocket обновляет кэш в фоне, этот адаптер только читает из кэша.
"""
from typing import Dict, List, Optional

from app.providers.base import BasePriceAdapter
from app.core.redis_client import get_redis
from app.core.coin_registry import coin_registry


class OKXPriceAdapter(BasePriceAdapter):
    """Адаптер для получения цен из OKX (через Redis кэш)"""
    
    def __init__(self):
        self.cache_ttl = 10  # TTL кэша цен в секундах
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        """
        Получить цену монеты из Redis кэша
        
        Args:
            coin_id: OKX символ (например, "BTC-USDT")
            
        Returns:
            {price, percent_change_24h, volume_24h} или None
        """
        # Находим внутренний ID монеты по OKX символу
        internal_coin = coin_registry.find_coin_by_external_id("okx", coin_id)
        if not internal_coin:
            return None
        
        # Читаем из Redis (ключ coin_price:{internal_id})
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            cache_key = f"coin_price:{internal_coin.id}"
            cached_data = await redis.get(cache_key)
            
            if cached_data:
                import json
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode('utf-8')
                price_data = json.loads(cached_data)
                return price_data
                
        except Exception as e:
            print(f"[OKXPriceAdapter] Ошибка чтения цены для {coin_id}: {e}")
        
        return None
    
    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Получить цены для нескольких монет
        
        Args:
            coin_ids: Список OKX символов
            
        Returns:
            Словарь {okx_symbol: {price, percent_change_24h, volume_24h}}
        """
        result = {}
        
        # Получаем все цены параллельно
        import asyncio
        tasks = [self.get_price(coin_id) for coin_id in coin_ids]
        prices = await asyncio.gather(*tasks)
        
        for coin_id, price_data in zip(coin_ids, prices):
            if price_data:
                result[coin_id] = price_data
        
        return result
    
    def is_available(self, coin_id: str) -> bool:
        """
        Проверить, доступна ли монета на OKX
        
        Args:
            coin_id: OKX символ (например, "BTC-USDT")
            
        Returns:
            True если монета есть в реестре с OKX маппингом
        """
        internal_coin = coin_registry.find_coin_by_external_id("okx", coin_id)
        return internal_coin is not None


# Глобальный экземпляр
okx_price_adapter = OKXPriceAdapter()

