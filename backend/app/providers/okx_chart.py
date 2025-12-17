"""
OKX Chart Provider

Chart provider from OKX REST API.
"""
from typing import Dict, List, Optional
from datetime import datetime

from app.providers.base_adapters import BaseChartAdapter
from app.core.coin_registry import coin_registry
from app.utils.formatters import format_chart_date


class OKXChartAdapter(BaseChartAdapter):

    

    BASE_URL = "https://www.okx.com/api/v5"
    
    # Period mapping to OKX intervals and candle counts
    # OKX uses intervals: 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M
    PERIOD_MAP = {
        "1d": {"bar": "5m", "limit": 288},  # 5 minutes * 288 = 24 hours
        "7d": {"bar": "1H", "limit": 168},  # 1 hour * 168 = 7 days
        "30d": {"bar": "4H", "limit": 180},  # 4 hours * 180 = 30 days
        "1y": {"bar": "1D", "limit": 365},   # 1 day * 365 = 1 year
    }
    
    async def get_chart_data(
        self,
        coin_id: str,
        period: str = "7d",
    ) -> Optional[List[Dict]]:

        try:
            # Get period configuration
            config = self.PERIOD_MAP.get(period)
            if not config:
                return None
            
            # Get historical data from OKX REST API
            # Parameters: instId, bar (interval), limit
            from app.utils.http_client import SharedHTTPClient
            client = SharedHTTPClient.get_client()
            
            url = f"{self.BASE_URL}/market/candles"
            params = {
                "instId": coin_id,
                "bar": config["bar"],
                "limit": config["limit"],
            }
            
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            # OKX response format: {"code": "0", "data": [[timestamp, open, high, low, close, volume, ...], ...]}
            if data.get("code") != "0":
                return None
            
            candles = data.get("data", [])
            if not candles:
                return None
            
            # Convert OKX candle data to our format
            # OKX candle format: [timestamp, open, high, low, close, volume, volCcy, volCcyQuote, confirm]
            chart_data = []
            for candle in candles:
                timestamp_ms = int(candle[0])
                close_price = float(candle[4])
                volume = float(candle[5])
                
                timestamp_seconds = timestamp_ms / 1000
                date_obj = datetime.fromtimestamp(timestamp_seconds) 
                date_str = format_chart_date(date_obj, period)
                
                chart_data.append({
                    "date": date_str,
                    "price": close_price,
                    "volume": volume,
                })
            
            # Sort by date (OKX returns in reverse order - newest to oldest)
            chart_data.sort(key=lambda x: x["date"])
            
            return chart_data
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def is_available(self, coin_id: str) -> bool:
        internal_coin = coin_registry.find_coin_by_external_id("okx", coin_id)
        return internal_coin is not None

okx_chart_adapter = OKXChartAdapter()