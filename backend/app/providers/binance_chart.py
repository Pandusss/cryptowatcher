"""
Binance Chart Provider

Провайдер графиков из Binance REST API.
"""
from typing import Dict, List, Optional
from datetime import datetime

from app.providers.base import BaseChartAdapter
from app.core.coin_registry import coin_registry
from app.utils.formatters import format_chart_date


class BinanceChartAdapter(BaseChartAdapter):
    """Адаптер для получения графиков из Binance REST API"""
    
    BASE_URL = "https://api.binance.com/api/v3"
    
    # Маппинг периодов на интервалы Binance и количество свечей
    PERIOD_MAP = {
        "1d": {"interval": "5m", "limit": 288},  # 5 минут * 288 = 24 часа
        "7d": {"interval": "1h", "limit": 168},  # 1 час * 168 = 7 дней
        "30d": {"interval": "4h", "limit": 180},  # 4 часа * 180 = 30 дней
        "1y": {"interval": "1d", "limit": 365},   # 1 день * 365 = 1 год
    }
    
    async def get_chart_data(
        self,
        coin_id: str,
        period: str = "7d",
    ) -> Optional[List[Dict]]:
        """
        Получить данные графика из Binance API
        
        Args:
            coin_id: Binance символ (например, "BTCUSDT")
            period: Период графика (1d, 7d, 30d, 1y)
            
        Returns:
            Список точек графика [{"date": str, "price": float, "volume": float}] или None
        """
        try:
            # Получаем конфигурацию периода
            config = self.PERIOD_MAP.get(period)
            if not config:
                print(f"[BinanceChartAdapter] Неподдерживаемый период: {period}")
                return None
            
            # Получаем исторические данные из Binance REST API
            from app.utils.http_client import SharedHTTPClient
            client = SharedHTTPClient.get_client()
            
            url = f"{self.BASE_URL}/klines"
            params = {
                "symbol": coin_id,
                "interval": config["interval"],
                "limit": config["limit"],
            }
            
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            klines = response.json()
            
            # Преобразуем данные Binance kline в наш формат
            # Формат Binance kline: [timestamp, open, high, low, close, volume, ...]
            chart_data = []
            for kline in klines:
                timestamp_ms = kline[0]  # Unix timestamp в миллисекундах
                close_price = float(kline[4])  # Используем цену закрытия
                volume = float(kline[5])
                
                # Преобразуем timestamp в строку даты
                timestamp_seconds = timestamp_ms / 1000
                date_obj = datetime.fromtimestamp(timestamp_seconds)
                date_str = format_chart_date(date_obj, period)
                
                chart_data.append({
                    "date": date_str,
                    "price": close_price,
                    "volume": volume,
                })
            
            # Сортируем по дате
            chart_data.sort(key=lambda x: x["date"])
            
            print(f"[BinanceChartAdapter] ✅ Получено {len(chart_data)} точек из Binance для {coin_id} ({period})")
            return chart_data
            
        except Exception as e:
            print(f"[BinanceChartAdapter] Ошибка получения данных из Binance для {coin_id}: {e}")
            return None
    
    def is_available(self, coin_id: str) -> bool:
        """
        Проверить, доступна ли монета на Binance
        
        Args:
            coin_id: Binance символ (например, "BTCUSDT")
            
        Returns:
            True если монета есть в реестре с Binance маппингом
        """
        internal_coin = coin_registry.find_coin_by_external_id("binance", coin_id)
        return internal_coin is not None


# Глобальный экземпляр
binance_chart_adapter = BinanceChartAdapter()

