"""
OKX Price Provider

Price provider from OKX WebSocket (via Redis cache).
WebSocket updates cache in background, this adapter only reads from cache.
"""
from typing import Dict, List, Optional

from app.providers.base_adapters import BasePriceAdapter
from app.core.coin_registry import coin_registry


class OKXPriceAdapter(BasePriceAdapter):
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        return await self._get_price_from_redis(coin_id, "okx", "OKXPriceAdapter")
    
    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        result = {}
        
        # Get all prices in parallel
        import asyncio
        tasks = [self.get_price(coin_id) for coin_id in coin_ids]
        prices = await asyncio.gather(*tasks)
        
        for coin_id, price_data in zip(coin_ids, prices):
            if price_data:
                result[coin_id] = price_data
        
        return result
    
    def is_available(self, coin_id: str) -> bool:
        return coin_registry.find_coin_by_external_id("okx", coin_id) is not None

okx_price_adapter = OKXPriceAdapter()