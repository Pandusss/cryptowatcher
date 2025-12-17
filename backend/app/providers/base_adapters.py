"""
Base classes for data provider adapters
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

logger = logging.getLogger(f"BaseAdapters")

class BasePriceAdapter(ABC):
    """Base class for price adapters"""
    
    @abstractmethod
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        """
        Get current coin price
        
        Args:
            coin_id: External coin ID for this provider
            
        Returns:
            Dictionary with data: {price, percent_change_24h, volume_24h} or None
        """
        pass
    
    @abstractmethod
    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Get prices for multiple coins
        
        Args:
            coin_ids: List of external coin IDs
            
        Returns:
            Dictionary {coin_id: {price, percent_change_24h, volume_24h}}
        """
        pass
    
    @abstractmethod
    def is_available(self, coin_id: str) -> bool:
        pass
    
    async def _get_price_from_redis(
        self,
        coin_id: str,
        source: str,
        adapter_name: str
    ) -> Optional[Dict]:
        """
        Common method for reading price from Redis cache
        
        Args:
            coin_id: External coin ID (e.g., "BTCUSDT" for Binance)
            source: Data source ("binance", "okx")
            adapter_name: Adapter name for logging (e.g., "BinancePriceAdapter")
            
        Returns:
            Dictionary with price data or None
        """
        from app.core.coin_registry import coin_registry
        from app.core.redis_client import get_redis
        import json
        
        # Find internal coin ID by external symbol
        internal_coin = coin_registry.find_coin_by_external_id(source, coin_id)
        if not internal_coin:
            return None
        
        # Get Redis client
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            # Form cache key
            cache_key = f"coin_price:{internal_coin.id}"
            cached_data = await redis.get(cache_key)
            
            if cached_data:
                # Deserialize JSON (handle bytes and str)
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode('utf-8')
                price_data = json.loads(cached_data)
                return price_data
                
        except Exception as e:
            logger.error(f"[{adapter_name}] Error reading price for {coin_id}: {e}")
    
        return None


class BaseChartAdapter(ABC):
    
    @abstractmethod
    async def get_chart_data(
        self,
        coin_id: str,
        period: str = "7d"
    ) -> Optional[List[Dict]]:
        """
        Get chart data
        
        Args:
            coin_id: External coin ID
            period: Period (1d, 7d, 30d, 1y)
            
        Returns:
            List of chart points [{"date": str, "price": float, "volume": float}] or None
        """
        pass
    
    @abstractmethod
    def is_available(self, coin_id: str) -> bool:
        """
        Check if coin is available on this provider
        
        Args:
            coin_id: External coin ID
            
        Returns:
            True if available, False otherwise
        """
        pass


