"""
Base Chart Adapter with common functionality
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime

from app.core.coin_registry import coin_registry
from app.utils.formatters import format_chart_date


class BaseChartAdapter(ABC):
    """Base class for all chart adapters"""
    
    # Common period mapping for all adapters
    COMMON_PERIOD_MAP = {
        "1d": {"interval": "5m", "limit": 288},  # 5m * 288 = 24h
        "7d": {"interval": "1h", "limit": 168},  # 1h * 168 = 7d
        "30d": {"interval": "4h", "limit": 180}, # 4h * 180 = 30d
        "1y": {"interval": "1d", "limit": 365},  # 1d * 365 = 1y
    }
    
    @abstractmethod
    async def _fetch_candles(self, coin_id: str, interval: str, limit: int) -> List:
        """Fetch candles from exchange API"""
        pass
    
    @abstractmethod
    def _get_api_symbol(self, coin_id: str) -> str:
        """Convert internal coin ID to exchange symbol"""
        pass
    
    def is_available(self, coin_id: str) -> bool:
        """Check if coin is available on this exchange"""
        internal_coin = coin_registry.find_coin_by_external_id(
            self.EXCHANGE_NAME, coin_id
        )
        return internal_coin is not None
    
    async def get_chart_data(
        self,
        coin_id: str,
        period: str = "7d",
    ) -> Optional[List[Dict]]:
        """Get chart data for a coin"""
        try:
            # Get period configuration
            config = self.COMMON_PERIOD_MAP.get(period)
            if not config:
                return None
            
            # Fetch candles from exchange
            candles = await self._fetch_candles(
                coin_id=coin_id,
                interval=config["interval"],
                limit=config["limit"]
            )
            
            if not candles:
                return None
            
            # Process and format candles
            return self._process_candles(candles, period)
            
        except Exception:
            return None
    
    def _process_candles(self, candles: List, period: str) -> List[Dict]:   
        """Process raw candles to chart format"""
        chart_data = []
        
        for candle in candles:
            timestamp = candle[0]
            close_price = float(candle[4])
            volume = float(candle[5]) if len(candle) > 5 else 0
            
            if isinstance(timestamp, str):
                timestamp = int(timestamp)
            
            timestamp_seconds = timestamp / 1000
            
            # Create datetime in UTC
            from datetime import datetime, timezone
            date_obj = datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc)
            
            # Return in ISO format with timezone
            date_str = date_obj.isoformat()  # Example: "2025-12-17T18:12:12+00:00"
            
            chart_data.append({
                "date": date_str,  # ISO format with timezone
                "price": close_price,
                "volume": volume,
            })
        
        chart_data.sort(key=lambda x: x["date"])
        return chart_data