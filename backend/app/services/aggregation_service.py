"""
AggregationService - агрегация данных из разных провайдеров

Централизованный сервис для получения данных о монетах из разных источников
с учетом приоритетов и fallback механизмов.
"""
from typing import Dict, List, Optional
import asyncio
import logging

from app.core.coin_registry import coin_registry
from app.providers.coingecko_static import coingecko_static_adapter
from app.providers.binance_price import binance_price_adapter
from app.providers.okx_price import okx_price_adapter
from app.providers.binance_chart import binance_chart_adapter
from app.providers.okx_chart import okx_chart_adapter
from app.utils.cache import CoinCacheManager


class AggregationService:
    
    def __init__(self):
        self.cache = CoinCacheManager()
        self._logger = logging.getLogger("AggregationService")
        
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
            self._logger.info(f"The graph is loaded from the CACHE for {coin_id} ({period}): {len(cached_data)} points")
            return cached_data
        
        # Получаем список провайдеров в порядке приоритета
        providers = coin.price_priority  # Используем те же провайдеры что и для цен
        
        # Пробуем получить график от каждого провайдера по порядку
        for provider_name in providers:
            provider = self.chart_providers.get(provider_name)
            if not provider:
                self._logger.warning(f"Provider {provider_name} not found for {coin_id}")
                continue
            
            # Получаем внешний ID для этого провайдера
            external_id = coin.external_ids.get(provider_name)
            if not external_id:
                self._logger.warning(f"The coin {coin_id} does not have an external ID for the provider {provider_name}")
                continue
            
            # Проверяем доступность
            if not provider.is_available(external_id):
                self._logger.warning(f"Provider {provider_name} is unavailable for {external_id}")
                continue
            
            # Пытаемся получить график
            try:
                chart_data = await provider.get_chart_data(external_id, period)
                if chart_data:
                    # Сохраняем в кэш (если провайдер еще не сохранил)
                    await self.cache.set_chart(coin_id, period, chart_data)
                    self._logger.info(f"The chart was uploaded from the {provider_name.upper()} platform for {coin_id} ({period}): {len(chart_data)} points")
                    return chart_data
                else:
                    self._logger.warning(f"Provider {provider_name} returned empty data for {coin_id}")
            except Exception as e:
                self._logger.error(f"Error getting a chart from {provider_name} for {coin_id}: {e}")
                continue
        
        # If none of the providers from price_priority returned the schedule, we try all available providers as a fallback
        self._logger.info(f"Trying a fallback on all available providers for {coin_id}")
        all_available_providers = list(self.chart_providers.keys())
        
        for provider_name in all_available_providers:
            # Skip the providers that have already tried above
            if provider_name in providers:
                continue
            
            provider = self.chart_providers.get(provider_name)
            if not provider:
                continue
            
            external_id = coin.external_ids.get(provider_name)
            if not external_id:
                continue
            
            if not provider.is_available(external_id):
                continue
            
            try:
                chart_data = await provider.get_chart_data(external_id, period)
                if chart_data:
                    await self.cache.set_chart(coin_id, period, chart_data)
                    self._logger.info(f"Fallback was successful: the chart was loaded from the {provider_name.upper()} site for {coin_id} ({period}): {len(chart_data)} points")
                    return chart_data
            except Exception as e:
                self._logger.error(f"Fallback error from {provider_name} for {coin_id}: {e}")
                continue
        
        # Если ни один провайдер не вернул график, возвращаем None
        self._logger.error(f"No chart was found for {coin_id} ({period}) from any provider.")
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