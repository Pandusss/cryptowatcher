"""
OKX Chart Provider
"""
from typing import List, Dict
from app.providers.base_chart import BaseChartAdapter


class OKXChartAdapter(BaseChartAdapter):
    """OKX chart adapter"""
    
    EXCHANGE_NAME = "okx"
    BASE_URL = "https://www.okx.com/api/v5"
    
    # OKX specific interval names
    INTERVAL_MAP = {
        "5m": "5m",
        "1h": "1H",
        "4h": "4H",
        "1d": "1D",
    }
    
    def _get_api_symbol(self, coin_id: str) -> str:
        """OKX uses symbols like BTC-USDT"""
        return coin_id.upper().replace('USDT', '-USDT')
    
    async def _fetch_candles(self, coin_id: str, interval: str, limit: int) -> List:
        """Fetch candles from OKX"""
        from app.utils.http_client import SharedHTTPClient
        client = SharedHTTPClient.get_client()
        
        url = f"{self.BASE_URL}/market/candles"
        params = {
            "instId": self._get_api_symbol(coin_id),
            "bar": self.INTERVAL_MAP.get(interval, interval),
            "limit": limit,
        }
        
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        
        # Check OKX response code
        if data.get("code") != "0":
            return []
        
        return data.get("data", [])


# Global instance
okx_chart_adapter = OKXChartAdapter()