"""
Binance Chart Provider
"""
from typing import List
from app.providers.base_chart import BaseChartAdapter


class BinanceChartAdapter(BaseChartAdapter):
    """Binance chart adapter"""
    
    EXCHANGE_NAME = "binance"
    BASE_URL = "https://api.binance.com/api/v3"
    
    def _get_api_symbol(self, coin_id: str) -> str:
        """Binance uses uppercase symbols like BTCUSDT"""
        return coin_id.upper()
    
    async def _fetch_candles(self, coin_id: str, interval: str, limit: int) -> List:
        """Fetch candles from Binance"""
        from app.utils.http_client import SharedHTTPClient
        client = SharedHTTPClient.get_client()
        
        url = f"{self.BASE_URL}/klines"
        params = {
            "symbol": self._get_api_symbol(coin_id),
            "interval": interval,
            "limit": limit,
        }
        
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()


# Global instance
binance_chart_adapter = BinanceChartAdapter()