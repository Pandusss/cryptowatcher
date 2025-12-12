"""
AggregationService - агрегация данных из разных провайдеров

Централизованный сервис для получения данных о монетах из разных источников
с учетом приоритетов и fallback механизмов.
"""
from typing import Dict, List, Optional
import asyncio

from app.core.coin_registry import coin_registry
from app.providers.coingecko_static import coingecko_static_adapter
from app.providers.binance_price import binance_price_adapter
from app.providers.okx_price import okx_price_adapter
from app.providers.binance_chart import binance_chart_adapter
from app.providers.okx_chart import okx_chart_adapter
from app.providers.coingecko_chart import coingecko_chart_adapter
from app.utils.cache import CoinCacheManager


class AggregationService:
    
    def __init__(self):
        self.cache = CoinCacheManager()
        
        # Регистр провайдеров
        self.static_providers = {
            "coingecko": coingecko_static_adapter,
        }
        
        self.price_providers = {
            "binance": binance_price_adapter,
            "okx": okx_price_adapter,
        }
        
        self.chart_providers = {
            "binance": binance_chart_adapter,
            "okx": okx_chart_adapter,
            "coingecko": coingecko_chart_adapter,
        }
    
    async def get_coin_static_data(self, coin_id: str) -> Optional[Dict]:

        coin = coin_registry.get_coin(coin_id)
        if not coin:
            return None
        
        # Используем CoinGecko для статики
        coingecko_id = coin.external_ids.get("coingecko")
        if not coingecko_id:
            return None
        
        return await self.static_providers["coingecko"].get_coin_static_data(coingecko_id)
    
    async def get_coins_static_data(self, coin_ids: List[str]) -> Dict[str, Dict]:

        # Получаем CoinGecko ID для всех монет
        coingecko_ids = []
        coin_id_map = {}  # coingecko_id -> internal_id
        
        for coin_id in coin_ids:
            coin = coin_registry.get_coin(coin_id)
            if coin:
                coingecko_id = coin.external_ids.get("coingecko")
                if coingecko_id:
                    coingecko_ids.append(coingecko_id)
                    coin_id_map[coingecko_id] = coin_id
        
        if not coingecko_ids:
            return {}
        
        # Получаем статику из CoinGecko
        static_data = await self.static_providers["coingecko"].get_coins_static_data(coingecko_ids)
        
        # Преобразуем обратно в internal_id
        result = {}
        for coingecko_id, data in static_data.items():
            internal_id = coin_id_map.get(coingecko_id)
            if internal_id:
                result[internal_id] = data
        
        return result
    
    async def get_coin_price(self, coin_id: str) -> Optional[Dict]:

        coin = coin_registry.get_coin(coin_id)
        if not coin:
            return None
        
        # Получаем список провайдеров в порядке приоритета
        providers = coin.price_priority
        
        # Пробуем получить цену от каждого провайдера по порядку
        for provider_name in providers:
            provider = self.price_providers.get(provider_name)
            if not provider:
                continue
            
            # Получаем внешний ID для этого провайдера
            external_id = coin.external_ids.get(provider_name)
            if not external_id:
                continue
            
            # Проверяем доступность
            if not provider.is_available(external_id):
                continue
            
            # Пытаемся получить цену
            price_data = await provider.get_price(external_id)
            if price_data:
                return price_data
        
        # Если ни один провайдер не вернул цену, возвращаем None
        return None
    
    async def get_coins_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:

        # Получаем цены параллельно
        tasks = [self.get_coin_price(coin_id) for coin_id in coin_ids]
        prices = await asyncio.gather(*tasks)
        
        result = {}
        for coin_id, price_data in zip(coin_ids, prices):
            if price_data:
                result[coin_id] = price_data
        
        return result
    
    async def get_coin_chart(
        self,
        coin_id: str,
        period: str = "7d"
    ) -> Optional[List[Dict]]:

        coin = coin_registry.get_coin(coin_id)
        if not coin:
            return None
        
        # Проверяем кэш
        cached_data = await self.cache.get_chart(coin_id, period)
        if cached_data:
            return cached_data
        
        # Получаем список провайдеров в порядке приоритета
        providers = coin.price_priority  # Используем те же провайдеры что и для цен
        
        # Пробуем получить график от каждого провайдера по порядку
        for provider_name in providers:
            provider = self.chart_providers.get(provider_name)
            if not provider:
                continue
            
            # Получаем внешний ID для этого провайдера
            external_id = coin.external_ids.get(provider_name)
            if not external_id:
                continue
            
            # Проверяем доступность
            if not provider.is_available(external_id):
                continue
            
            # Пытаемся получить график
            chart_data = await provider.get_chart_data(external_id, period)
            if chart_data:
                # Сохраняем в кэш (если провайдер еще не сохранил)
                await self.cache.set_chart(coin_id, period, chart_data)
                return chart_data
        
        # Fallback на CoinGecko если есть (теперь через адаптер)
        coingecko_id = coin.external_ids.get("coingecko")
        if coingecko_id:
            coingecko_provider = self.chart_providers.get("coingecko")
            if coingecko_provider and coingecko_provider.is_available(coingecko_id):
                chart_data = await coingecko_provider.get_chart_data(coingecko_id, period)
                if chart_data:
                    await self.cache.set_chart(coin_id, period, chart_data)
                    return chart_data
        
        return None
    
    async def get_coin_image_url(self, coin_id: str) -> Optional[str]:

        coin = coin_registry.get_coin(coin_id)
        if not coin:
            return None
        
        coingecko_id = coin.external_ids.get("coingecko")
        if not coingecko_id:
            return None
        
        return await self.static_providers["coingecko"].get_coin_image_url(coingecko_id)
    
    async def get_coin_details(self, coin_id: str) -> Optional[Dict]:

        # Получаем статику и цену параллельно
        static_task = self.get_coin_static_data(coin_id)
        price_task = self.get_coin_price(coin_id)
        
        static_data, price_data = await asyncio.gather(static_task, price_task)
        
        if not static_data:
            return None
        
        # Объединяем данные
        result = static_data.copy()
        
        if price_data:
            result["currentPrice"] = price_data.get("price", 0)
            result["priceChange24h"] = price_data.get("percent_change_24h", 0)
            result["volume24h"] = price_data.get("volume_24h", 0)
        else:
            result["currentPrice"] = 0
            result["priceChange24h"] = 0
            result["volume24h"] = 0
        
        return result

# Глобальный экземпляр
aggregation_service = AggregationService()