"""
Binance Price Provider

Провайдер цен из Binance WebSocket (через Redis кэш).
WebSocket обновляет кэш в фоне, этот адаптер только читает из кэша.
"""
from typing import Dict, List, Optional

from app.providers.base import BasePriceAdapter
from app.core.redis_client import get_redis
from app.core.coin_registry import coin_registry


class BinancePriceAdapter(BasePriceAdapter):
    """Адаптер для получения цен из Binance (через Redis кэш)"""
    
    def __init__(self):
        self.cache_ttl = 10  # TTL кэша цен в секундах
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        """
        Получить цену монеты из Redis кэша
        
        Args:
            coin_id: Binance символ (например, "BTCUSDT")
            
        Returns:
            {price, percent_change_24h, volume_24h} или None
        """
        # Находим внутренний ID монеты по Binance символу
        internal_coin = coin_registry.find_coin_by_external_id("binance", coin_id)
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
                price_data = json.loads(cached_data)
                return price_data
                
        except Exception as e:
            print(f"[BinancePriceAdapter] Ошибка чтения цены для {coin_id}: {e}")
        
        return None
    
    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Получить цены для нескольких монет
        
        Args:
            coin_ids: Список Binance символов
            
        Returns:
            Словарь {binance_symbol: {price, percent_change_24h, volume_24h}}
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
        Проверить, доступна ли монета на Binance
        
        Args:
            coin_id: Binance символ (например, "BTCUSDT")
            
        Returns:
            True если монета есть в реестре с Binance маппингом
        """
        internal_coin = coin_registry.find_coin_by_external_id("binance", coin_id)
        return internal_coin is not None


# Глобальный экземпляр
binance_price_adapter = BinancePriceAdapter()

