"""
CoinGecko Static Data Provider

Только статические данные (id, name, symbol, imageUrl).
Не предоставляет цены - для этого используются биржи.
"""
from typing import Dict, List, Optional

from app.providers.base import BaseStaticAdapter
from app.providers.coingecko_client import CoinGeckoClient
from app.utils.cache import CoinCacheManager


class CoinGeckoStaticAdapter(BaseStaticAdapter):    
    def __init__(self):
        self.client = CoinGeckoClient()
        self.cache = CoinCacheManager()
    
    async def get_coin_static_data(self, coin_id: str) -> Optional[Dict]:
        cached = await self.cache.get_static(coin_id)
        if cached:
            return cached
        
        try:
            coin_data = await self.client.get(f"/coins/{coin_id}")
            
            static_data = {
                "id": coin_data.get("id"),
                "name": coin_data.get("name"),
                "symbol": coin_data.get("symbol", "").upper(),
                "imageUrl": coin_data.get("image", {}).get("large") or coin_data.get("image", {}).get("small"),
            }
            
            await self.cache.set_static(coin_id, static_data)
            
            return static_data
            
        except Exception as e:
            print(f"[CoinGeckoStaticAdapter] Ошибка получения статики для {coin_id}: {e}")
            return None
    
    async def get_coins_static_data(self, coin_ids: List[str]) -> Dict[str, Dict]:
        if not coin_ids:
            return {}
        
        result = {}
        ids_to_fetch = []
        
        for coin_id in coin_ids:
            cached = await self.cache.get_static(coin_id)
            if cached:
                result[coin_id] = cached
            else:
                ids_to_fetch.append(coin_id)
        
        if not ids_to_fetch:
            return result
        
        try:
            # Batch запрос через /coins/markets
            ids_param = ",".join(ids_to_fetch)
            coins_data = await self.client.get(
                "/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": ids_param,
                    "order": "market_cap_desc",
                    "per_page": len(ids_to_fetch),
                    "sparkline": False,
                },
            )
            
            # Формируем результат
            for coin_data in coins_data:
                coin_id = coin_data.get("id")
                if coin_id in ids_to_fetch:
                    static_data = {
                        "id": coin_id,
                        "name": coin_data.get("name"),
                        "symbol": coin_data.get("symbol", "").upper(),
                        "imageUrl": coin_data.get("image"),
                    }
                    result[coin_id] = static_data
                    await self.cache.set_static(coin_id, static_data)
            
            print(f"[CoinGeckoStaticAdapter] Получено статики: {len(result)} из {len(coin_ids)} запрошенных")
            
        except Exception as e:
            print(f"[CoinGeckoStaticAdapter] Ошибка batch запроса статики: {e}")
        
        return result
    
    async def get_coin_image_url(self, coin_id: str) -> Optional[str]:
        static_data = await self.get_coin_static_data(coin_id)
        if static_data:
            return static_data.get("imageUrl")
        return None
    
    async def close(self):
        await self.client.close()

coingecko_static_adapter = CoinGeckoStaticAdapter()

