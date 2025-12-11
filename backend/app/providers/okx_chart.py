"""
OKX Chart Provider

Провайдер графиков из OKX REST API.
"""
from typing import Dict, List, Optional
from datetime import datetime

from app.providers.base import BaseChartAdapter
from app.core.coin_registry import coin_registry


class OKXChartAdapter(BaseChartAdapter):
    """Адаптер для получения графиков из OKX REST API"""
    
    BASE_URL = "https://www.okx.com/api/v5"
    
    # Маппинг периодов на интервалы OKX и количество свечей
    # OKX использует интервалы: 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M
    PERIOD_MAP = {
        "1d": {"bar": "5m", "limit": 288},  # 5 минут * 288 = 24 часа
        "7d": {"bar": "1H", "limit": 168},  # 1 час * 168 = 7 дней
        "30d": {"bar": "4H", "limit": 180},  # 4 часа * 180 = 30 дней
        "1y": {"bar": "1D", "limit": 365},   # 1 день * 365 = 1 год
    }
    
    async def get_chart_data(
        self,
        coin_id: str,
        period: str = "7d",
    ) -> Optional[List[Dict]]:
        """
        Получить данные графика из OKX API
        
        Args:
            coin_id: OKX символ (например, "BTC-USDT")
            period: Период графика (1d, 7d, 30d, 1y)
            
        Returns:
            Список точек графика [{"date": str, "price": float, "volume": float}] или None
        """
        try:
            # Получаем конфигурацию периода
            config = self.PERIOD_MAP.get(period)
            if not config:
                print(f"[OKXChartAdapter] Неподдерживаемый период: {period}")
                return None
            
            # Получаем исторические данные из OKX REST API
            # OKX API: GET /api/v5/market/candles
            # Параметры: instId, bar (интервал), limit
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
            
            # OKX формат ответа: {"code": "0", "data": [[timestamp, open, high, low, close, volume, ...], ...]}
            if data.get("code") != "0":
                print(f"[OKXChartAdapter] Ошибка API OKX: {data.get('msg', 'Unknown error')}")
                return None
            
            candles = data.get("data", [])
            if not candles:
                print(f"[OKXChartAdapter] Пустой ответ от OKX для {coin_id}")
                return None
            
            # Преобразуем данные OKX candle в наш формат
            # Формат OKX candle: [timestamp, open, high, low, close, volume, volCcy, volCcyQuote, confirm]
            # timestamp в миллисекундах (строковое представление)
            chart_data = []
            for candle in candles:
                timestamp_ms = int(candle[0])  # Unix timestamp в миллисекундах (строка)
                close_price = float(candle[4])  # Используем цену закрытия
                volume = float(candle[5])  # Объем в базовой валюте
                
                # Преобразуем timestamp в строку даты
                timestamp_seconds = timestamp_ms / 1000
                date_obj = datetime.fromtimestamp(timestamp_seconds)
                
                # Форматируем дату в зависимости от периода
                if period == "1d":
                    date_str = date_obj.strftime("%Y-%m-%d %H:%M")
                elif period == "7d":
                    date_str = date_obj.strftime("%Y-%m-%d %H:%M")
                elif period == "30d":
                    date_str = date_obj.strftime("%Y-%m-%d 00:00")
                else:  # 1y
                    date_str = date_obj.strftime("%Y-%m-%d 00:00")
                
                chart_data.append({
                    "date": date_str,
                    "price": close_price,
                    "volume": volume,
                })
            
            # Сортируем по дате (OKX возвращает в обратном порядке - от новых к старым)
            chart_data.sort(key=lambda x: x["date"])
            
            print(f"[OKXChartAdapter] ✅ Получено {len(chart_data)} точек из OKX для {coin_id} ({period})")
            return chart_data
            
        except Exception as e:
            print(f"[OKXChartAdapter] Ошибка получения данных из OKX для {coin_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def is_available(self, coin_id: str) -> bool:
        """
        Проверить, доступна ли монета на OKX
        
        Args:
            coin_id: OKX символ (например, "BTC-USDT")
            
        Returns:
            True если монета есть в реестре с OKX маппингом
        """
        internal_coin = coin_registry.find_coin_by_external_id("okx", coin_id)
        return internal_coin is not None


# Глобальный экземпляр
okx_chart_adapter = OKXChartAdapter()

