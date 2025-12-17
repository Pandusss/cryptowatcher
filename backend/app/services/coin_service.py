"""
Main service for working with cryptocurrencies (public interface)

Architecture:
- CoinStaticService: static data from CoinGecko
- CoinPriceService: prices from Redis/WebSocket
- CoinCacheService: working with cache
- CoinService: business logic orchestration

Notes:
- CoinGecko is used ONLY for static data (id, name, symbol, imageUrl)
- Prices are obtained from Binance/OKX WebSocket (binance_websocket.py, okx_websocket.py)
- Charts are obtained from Binance/OKX (binance_chart.py, okx_chart.py)
"""
import hashlib
import logging
import asyncio
from typing import Dict, List, Any, Optional

from app.core.redis_client import get_redis
from app.services.coin_static_service import CoinStaticService
from app.services.coin_price_service import CoinPriceService
from app.services.coin_cache_service import CoinCacheService
from app.utils.formatters import get_price_decimals


class CoinService:
    
    def __init__(self):
        self.static_service = CoinStaticService()
        self.price_service = CoinPriceService()
        self.cache_service = CoinCacheService()
        self._logger = logging.getLogger("CoinService")

    
    async def close(self):
        await self.static_service.close()
    
    
    def _load_coins_config(self) -> tuple[List[str], str]:
        """
        Load coin list from registry and calculate config hash.
        """
        try:
            from app.core.coin_registry import coin_registry
            
            # Get all enabled coins from registry (automatically reloads config on change)
            coin_ids = coin_registry.get_coin_ids(enabled_only=True)
            
            # Use hash of entire config from CoinRegistry (includes all changes, including coin contents)
            config_hash = coin_registry.get_config_hash() or hashlib.md5(','.join(coin_ids).encode()).hexdigest()
            
            self._logger.info(f"Loaded {len(coin_ids)} coins from CoinRegistry (hash: {config_hash[:8]}...)")
            return coin_ids, config_hash
        except Exception as e:
            self._logger.error(f"Error loading coins from CoinRegistry: {e}")
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
            return [], ""
    
    def _format_coin_data(self, static_data: Dict, price_data: Optional[Dict] = None) -> Dict:
        """
        Format coin data for API response.
        """
        if price_data:
            price = price_data.get("price", 0)
            percent_change_24h = price_data.get("percent_change_24h", 0)
            volume_24h = price_data.get("volume_24h", 0)
            price_decimals = price_data.get("priceDecimals", get_price_decimals(price))
        else:
            price = 0
            percent_change_24h = 0
            volume_24h = 0
            price_decimals = 2
        
        return {
            "id": static_data.get("id", ""),
            "name": static_data.get("name", ""),
            "symbol": static_data.get("symbol", "").upper(),
            "slug": static_data.get("slug", ""),
            "imageUrl": static_data.get("imageUrl", ""),
            "quote": {
                "USD": {
                    "price": price,
                    "percent_change_24h": percent_change_24h,
                    "volume_24h": volume_24h,
                }
            },
            "priceDecimals": price_decimals,
        }
    
    async def get_crypto_list_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Get prices for coin list ONLY from Redis (updated via Binance/OKX WebSocket).
        CoinGecko is NOT used for prices - only for static data (images, names).
        """
        return await self.price_service.get_crypto_list_prices(coin_ids)
    
    async def get_crypto_list(
        self,
        limit: int = 100,
        page: int = 1,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """
        Get list of coins with static data and prices.
        
        Args:
            limit: maximum number of coins (not used in current implementation)
            page: page number (not used)
            force_refresh: force data refresh
            
        Returns:
            List of formatted coins
        """
        config_coins, config_hash = self._load_coins_config()
        
        if not config_coins:
            self._logger.info("Config file is empty, returning empty list")
            return []
        
        # Check if config has changed (by hash)
        redis = await get_redis()
        if redis:
            cached_hash_key = "coins_list:config_hash"
            cached_hash_raw = await redis.get(cached_hash_key)
            
            # Process data from Redis (could be bytes or str)
            cached_hash = None
            if cached_hash_raw:
                if isinstance(cached_hash_raw, bytes):
                    cached_hash = cached_hash_raw.decode('utf-8')
                else:
                    cached_hash = str(cached_hash_raw)
            
            if cached_hash and cached_hash != config_hash:
                # Clear coin list cache
                await redis.delete("coins_list:filtered")
                # Clear static cache for all coins
                await self.cache_service.clear_all_static_cache()
                
                # Update hash
                await redis.set(cached_hash_key, config_hash)
            elif not cached_hash:
                # First run - save hash
                await redis.set(cached_hash_key, config_hash)
        
        self._logger.info(f"[get_crypto_list] Total coins in config: {len(config_coins)}")
        
        # Get data from cache
        cached_data = await self.cache_service.get_static_and_prices_batch(config_coins)
        
        # Analyze cache
        formatted_coins = []
        coins_to_fetch = []
        coins_with_full_cache = 0
        coins_with_static_only = 0
        coins_with_no_cache = 0
        
        for coin_id in config_coins:
            coin_cache = cached_data.get(coin_id, {"static": None, "price": None})
            cached_static = coin_cache.get("static")
            cached_price = coin_cache.get("price")
            
            if cached_static:
                if cached_price:
                    # Fully in cache
                    coin = self._format_coin_data(cached_static, cached_price)
                    formatted_coins.append(coin)
                    coins_with_full_cache += 1
                else:
                    # Only static data in cache
                    coin = self._format_coin_data(cached_static, None)
                    formatted_coins.append(coin)
                    coins_with_static_only += 1
            else:
                # Not in cache
                coins_with_no_cache += 1
                coins_to_fetch.append(coin_id)
        
        # If force_refresh, load everything again
        if force_refresh:
            coins_to_fetch = config_coins.copy()
            coins_with_no_cache = len(config_coins)
            formatted_coins = []  # Discard cached data
            
        # If everything is in cache and no forced refresh needed, return immediately
        if formatted_coins and not coins_to_fetch:
            # Sort by order from config
            coin_order = {coin_id: idx for idx, coin_id in enumerate(config_coins)}
            formatted_coins.sort(key=lambda x: coin_order.get(x.get("id"), 9999))
            return formatted_coins
        
        # Load static data for coins not in cache
        if coins_to_fetch:
            
            # Use CoinStaticService for loading
            static_data_dict = await self.static_service.get_static_data_batch(coins_to_fetch)
            
            # Get prices for loaded coins
            price_data_dict = await self.price_service.get_prices_for_formatting(coins_to_fetch)
            
            # Form final list
            for coin_id in coins_to_fetch:
                static_data = static_data_dict.get(coin_id)
                if not static_data:
                    self._logger.warning(f"Coin {coin_id} not found in API response")
                    continue
                    
                price_data = price_data_dict.get(coin_id)
                coin = self._format_coin_data(static_data, price_data)
                formatted_coins.append(coin)
        
        # Sort by order from config
        coin_order = {coin_id: idx for idx, coin_id in enumerate(config_coins)}
        formatted_coins.sort(key=lambda x: coin_order.get(x.get("id"), 9999))
        
        return formatted_coins
    
    async def get_crypto_details(self, coin_id: str) -> Dict:
        """
        Get detailed information about a coin.
        """
        # Get static data
        static_data = await self.static_service.get_static_data(coin_id)
        if not static_data:
            # If no static data, try to get via cache
            static_data = await self.cache_service.get_static(coin_id)
            if not static_data:
                return {
                    "id": coin_id,
                    "name": "",
                    "symbol": "",
                    "currentPrice": 0,
                    "priceChange24h": 0,
                    "priceChangePercent24h": 0,
                    "imageUrl": "",
                    "priceDecimals": 2,
                }
        
        # Get price
        price_data = await self.price_service.get_price(coin_id)
        
        price = price_data.get("price", 0) if price_data else 0
        price_change_24h = price_data.get("volume_24h", 0) if price_data else 0
        price_change_percent_24h = price_data.get("percent_change_24h", 0) if price_data else 0
        price_decimals = price_data.get("priceDecimals", get_price_decimals(price)) if price_data else get_price_decimals(price)
        
        coin = {
            "id": static_data.get("id", coin_id),
            "name": static_data.get("name", ""),
            "symbol": static_data.get("symbol", "").upper(),
            "currentPrice": price,
            "priceChange24h": price_change_24h,
            "priceChangePercent24h": price_change_percent_24h,
            "imageUrl": static_data.get("imageUrl", ""),
            "priceDecimals": price_decimals,
        }
        
        return coin
    
    async def refresh_coin_data(self, coin_id: str) -> bool:
        """
        Force refresh coin data.
        """
        try:
            # Clear static cache
            await self.cache_service.clear_static_cache(coin_id)
            
            # Clear price cache
            await self.cache_service.clear_price_cache(coin_id)
            
            # Load again
            static_data = await self.static_service.get_static_data(coin_id)
            return static_data is not None
        except Exception as e:
            
            self._logger.error(f"Error refreshing data for {coin_id}: {e}")
            return False