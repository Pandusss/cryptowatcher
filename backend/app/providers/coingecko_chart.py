"""
CoinGecko Chart Provider

Провайдер графиков из CoinGecko REST API.
"""
from typing import Dict, List, Optional
from datetime import datetime

from app.providers.base import BaseChartAdapter
from app.providers.coingecko_client import CoinGeckoClient
from app.utils.cache import CoinCacheManager
from app.utils.formatters import format_chart_date


class CoinGeckoChartAdapter(BaseChartAdapter):
    def __init__(self):
        self.client = CoinGeckoClient()
        self.cache = CoinCacheManager()
    
    async def get_chart_data(
        self,
        coin_id: str,
        period: str = "7d",
    ) -> Optional[List[Dict]]:
        # Проверяем кэш
        cached_data = await self.cache.get_chart(coin_id, period)
        if cached_data:
            return cached_data
        
        # Маппинг периодов на дни для CoinGecko API
        days_map = {
            "1d": 1,
            "7d": 7,
            "30d": 30,
            "1y": 365,
        }
        days = days_map.get(period, 7)
        
        try:
            # Получаем исторические данные через CoinGecko market_chart endpoint
            chart_data_response = await self.client.get(
                f"/coins/{coin_id}/market_chart",
                params={
                    "vs_currency": "usd",
                    "days": days,
                },
            )
            
            # Парсим данные графика
            prices = chart_data_response.get("prices", [])
            volumes = chart_data_response.get("total_volumes", [])
            
            chart_data = []
            
            # Объединяем цены и объемы
            for i, price_point in enumerate(prices):
                timestamp_ms = price_point[0]  # Unix timestamp в миллисекундах
                price = price_point[1]
                
                # Находим соответствующий объем
                volume = 0
                if volumes and i < len(volumes):
                    volume = volumes[i][1] if len(volumes[i]) > 1 else 0
                
                timestamp_seconds = timestamp_ms / 1000
                date_obj = datetime.fromtimestamp(timestamp_seconds)
                date_str = format_chart_date(date_obj, period)
                
                chart_data.append({
                    "date": date_str,
                    "price": float(price),
                    "volume": float(volume) if volume else 0,
                })
            
            # Сортируем по дате
            chart_data.sort(key=lambda x: x["date"])
            
            # Сохраняем в кэш
            if chart_data:
                await self.cache.set_chart(coin_id, period, chart_data)
            
            print(f"[CoinGeckoChartAdapter] ✅ Получено {len(chart_data)} точек из CoinGecko для {coin_id} ({period})")
            return chart_data if chart_data else None
            
        except Exception as e:
            print(f"[CoinGeckoChartAdapter] Ошибка получения данных из CoinGecko для {coin_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def is_available(self, coin_id: str) -> bool:
        from app.core.coin_registry import coin_registry
        coin = coin_registry.find_coin_by_external_id("coingecko", coin_id)
        return coin is not None

# Глобальный экземпляр
coingecko_chart_adapter = CoinGeckoChartAdapter()

