"""
Binance Price Provider

Провайдер цен из Binance WebSocket (через Redis кэш).
WebSocket обновляет кэш в фоне, этот адаптер только читает из кэша.
"""
from typing import Dict, List, Optional

from app.providers.base import BasePriceAdapter
from app.core.coin_registry import coin_registry


class BinancePriceAdapter(BasePriceAdapter):

    def __init__(self):
        self.cache_ttl = 10  # TTL кэша цен в секундах
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        return await self._get_price_from_redis(coin_id, "binance", "BinancePriceAdapter")
    
    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
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
        return coin_registry.find_coin_by_external_id("binance", coin_id) is not None

# Глобальный экземпляр
binance_price_adapter = BinancePriceAdapter()

