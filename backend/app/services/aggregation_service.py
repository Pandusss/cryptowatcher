"""
AggregationService - data aggregation from different providers

Centralized service for getting coin data from different sources
with priority and fallback mechanisms.
"""
from typing import Dict, List, Optional
import asyncio
import logging

from app.core.coin_registry import coin_registry
from app.providers.coingecko_static import coingecko_static_adapter
from app.providers.binance_price import binance_price_adapter
from app.providers.okx_price import okx_price_adapter
from app.providers.mexc_price import mexc_price_adapter
from app.providers.binance_chart import binance_chart_adapter
from app.providers.okx_chart import okx_chart_adapter
from app.providers.mexc_chart import mexc_chart_adapter
from app.utils.cache import CoinCacheManager


class AggregationService:
    
    def __init__(self):
        self.cache = CoinCacheManager()
        self._logger = logging.getLogger("AggregationService")
        
        # Provider registry
        self.static_providers = {
            "coingecko": coingecko_static_adapter,
        }
        
        self.price_providers = {
            "binance": binance_price_adapter,
            "okx": okx_price_adapter,
            "mexc": mexc_price_adapter,
        }
        
        self.chart_providers = {
            "binance": binance_chart_adapter,
            "okx": okx_chart_adapter,
            "mexc": mexc_chart_adapter,
        }
    
    async def get_coin_static_data(self, coin_id: str) -> Optional[Dict]:
        coin = coin_registry.get_coin(coin_id)
        if not coin:
            return None
        
        # Use CoinGecko for static data
        coingecko_id = coin.external_ids.get("coingecko")
        if not coingecko_id:
            return None
        
        return await self.static_providers["coingecko"].get_coin_static_data(coingecko_id)
    
    async def get_coins_static_data(self, coin_ids: List[str]) -> Dict[str, Dict]:
        # Get CoinGecko IDs for all coins
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
        
        # Get static data from CoinGecko
        static_data = await self.static_providers["coingecko"].get_coins_static_data(coingecko_ids)
        
        # Convert back to internal_id
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
        
        # Get provider list in priority order
        providers = coin.price_priority
        
        # Try to get price from each provider in order
        for provider_name in providers:
            provider = self.price_providers.get(provider_name)
            if not provider:
                continue
            
            # Get external ID for this provider
            external_id = coin.external_ids.get(provider_name)
            if not external_id:
                continue
            
            # Check availability
            if not provider.is_available(external_id):
                continue
            
            # Try to get price
            price_data = await provider.get_price(external_id)
            if price_data:
                return price_data
        
        # If no provider returned price, return None
        return None
    
    async def get_coins_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        # Get prices in parallel
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
        
        # Check cache
        cached_data = await self.cache.get_chart(coin_id, period)
        if cached_data:
            self._logger.info(f"Chart loaded from CACHE for {coin_id} ({period}): {len(cached_data)} points")
            return cached_data
        
        # Get provider list in priority order
        providers = coin.price_priority  # Use same providers as for prices
        
        # Try to get chart from each provider in order
        for provider_name in providers:
            provider = self.chart_providers.get(provider_name)
            if not provider:
                self._logger.warning(f"Provider {provider_name} not found for {coin_id}")
                continue
            
            # Get external ID for this provider
            external_id = coin.external_ids.get(provider_name)
            if not external_id:
                self._logger.warning(f"Coin {coin_id} doesn't have external ID for provider {provider_name}")
                continue
            
            # Check availability
            if not provider.is_available(external_id):
                self._logger.warning(f"Provider {provider_name} is unavailable for {external_id}")
                continue
            
            # Try to get chart
            try:
                chart_data = await provider.get_chart_data(external_id, period)
                if chart_data:
                    # Save to cache (if provider hasn't already saved)
                    await self.cache.set_chart(coin_id, period, chart_data)
                    self._logger.info(f"Chart loaded from {provider_name.upper()} for {coin_id} ({period}): {len(chart_data)} points")
                    return chart_data
                else:
                    self._logger.warning(f"Provider {provider_name} returned empty data for {coin_id}")
            except Exception as e:
                self._logger.error(f"Error getting chart from {provider_name} for {coin_id}: {e}")
                continue
        
        # If none of the providers from price_priority returned chart, try all available providers as fallback
        self._logger.info(f"Trying fallback to all available providers for {coin_id}")
        all_available_providers = list(self.chart_providers.keys())
        
        for provider_name in all_available_providers:
            # Skip providers already tried above
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
                    self._logger.info(f"Fallback successful: chart loaded from {provider_name.upper()} for {coin_id} ({period}): {len(chart_data)} points")
                    return chart_data
            except Exception as e:
                self._logger.error(f"Fallback error from {provider_name} for {coin_id}: {e}")
                continue
        
        # If no provider returned chart, return None
        self._logger.error(f"No chart found for {coin_id} ({period}) from any provider.")
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
        # Get static data and price in parallel
        static_task = self.get_coin_static_data(coin_id)
        price_task = self.get_coin_price(coin_id)
        
        static_data, price_data = await asyncio.gather(static_task, price_task)
        
        if not static_data:
            return None
        
        # Combine data
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

# Global instance
aggregation_service = AggregationService()