"""
CoinGecko Chart Provider

Chart provider from CoinGecko REST API (via HTTP requests).
Fetches historical price data via /coins/{id}/market_chart endpoint.
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone

from app.providers.base_chart import BaseChartAdapter
from app.providers.coingecko_client import CoinGeckoClient
from app.core.coin_registry import coin_registry

logger = logging.getLogger("CoinGeckoChart")


class CoinGeckoChartAdapter(BaseChartAdapter):
    """CoinGecko chart adapter"""
    
    EXCHANGE_NAME = "coingecko"
    
    # Period to days mapping for CoinGecko API
    PERIOD_TO_DAYS = {
        "1d": 1,
        "7d": 7,
        "30d": 30,
        "1y": 365,
    }
    
    def __init__(self):
        self.client = CoinGeckoClient()
    
    def _get_api_symbol(self, coin_id: str) -> str:
        """CoinGecko uses coin IDs like 'bitcoin', 'ethereum'"""
        return coin_id.lower()
    
    async def _fetch_candles(self, coin_id: str, interval: str, limit: int) -> List:
        """
        Fetch chart data from CoinGecko
        
        Note: CoinGecko doesn't use interval/limit like exchanges.
        Instead, we use the period parameter to determine days.
        This method signature is kept for compatibility with BaseChartAdapter.
        """
        # This method is not used directly - get_chart_data is overridden
        return []
    
    async def get_chart_data(
        self,
        coin_id: str,
        period: str = "7d",
    ) -> Optional[List[Dict]]:
        """
        Get chart data for a coin from CoinGecko
        
        Args:
            coin_id: CoinGecko coin ID (e.g., "bitcoin")
            period: Period (1d, 7d, 30d, 1y)
            
        Returns:
            List of chart points [{"date": str, "price": float, "volume": float}]
        """
        try:
            # Get days from period
            days = self.PERIOD_TO_DAYS.get(period)
            if not days:
                logger.warning(f"Unknown period: {period}")
                return None
            
            # Fetch market chart data
            response = await self.client.get(
                f"/coins/{coin_id}/market_chart",
                params={
                    "vs_currency": "usd",
                    "days": days,
                }
            )
            
            if not response:
                return None
            
            # Extract prices and volumes
            prices = response.get("prices", [])
            volumes = response.get("total_volumes", [])
            
            if not prices:
                return None
            
            # Create a map of timestamp -> volume for quick lookup
            volume_map = {vol[0]: vol[1] for vol in volumes}
            
            # Process data points
            chart_data = []
            for price_point in prices:
                timestamp_ms = price_point[0]
                price = float(price_point[1])
                
                # Get volume for this timestamp (or 0 if not found)
                volume = float(volume_map.get(timestamp_ms, 0))
                
                # Convert timestamp from milliseconds to seconds
                timestamp_seconds = timestamp_ms / 1000
                
                # Create datetime in UTC
                date_obj = datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc)
                
                # Return in ISO format with timezone
                date_str = date_obj.isoformat()
                
                chart_data.append({
                    "date": date_str,
                    "price": price,
                    "volume": volume,
                })
            
            # Sort by date
            chart_data.sort(key=lambda x: x["date"])
            
            return chart_data
            
        except Exception as e:
            logger.error(f"Error fetching chart data for {coin_id} ({period}): {e}")
            return None
    
    def is_available(self, coin_id: str) -> bool:
        """
        Check if coin is available on CoinGecko
        
        Args:
            coin_id: CoinGecko coin ID
            
        Returns:
            True if coin exists and coingecko is in price_priority
        """
        coin = coin_registry.find_coin_by_external_id("coingecko", coin_id)
        if not coin:
            return False
        
        # Check if coingecko is in price_priority (same logic as price adapter)
        return "coingecko" in coin.price_priority
    
    async def close(self):
        """Close HTTP client"""
        await self.client.close()


# Global instance
coingecko_chart_adapter = CoinGeckoChartAdapter()

