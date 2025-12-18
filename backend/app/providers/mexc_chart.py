"""
MEXC Chart Provider
"""
from typing import List
from app.providers.base_chart import BaseChartAdapter


class MEXCChartAdapter(BaseChartAdapter):
    """MEXC chart adapter"""
    
    EXCHANGE_NAME = "mexc"
    BASE_URL = "https://api.mexc.com/api/v3"
    
    # MEXC uses different interval format for some periods
    # 1h -> 60m, 1w -> not supported (use 1d with more limit)
    COMMON_PERIOD_MAP = {
        "1d": {"interval": "5m", "limit": 288},   # 5m * 288 = 24h
        "7d": {"interval": "60m", "limit": 168},  # 60m instead of 1h
        "30d": {"interval": "4h", "limit": 180},  # 4h * 180 = 30d
        "1y": {"interval": "1d", "limit": 365},   # 1d * 365 = 1y
    }
    
    def _get_api_symbol(self, coin_id: str) -> str:
        """MEXC uses uppercase symbols like BTCUSDT"""
        return coin_id.upper()
    
    async def _fetch_candles(self, coin_id: str, interval: str, limit: int) -> List:
        """Fetch candles from MEXC"""
        from app.utils.http_client import SharedHTTPClient
        client = SharedHTTPClient.get_client()
        
        url = f"{self.BASE_URL}/klines"
        params = {
            "symbol": self._get_api_symbol(coin_id),
            "interval": interval,
            "limit": limit,
        }
        
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()


# Global instance
mexc_chart_adapter = MEXCChartAdapter()
