"""
Утилиты для форматирования данных
"""
from typing import Union
from datetime import datetime, timezone

def get_price_decimals(price: Union[float, int]) -> int:
    """
    Определить количество знаков после запятой для цены
    
    Args:
        price: Цена монеты
        
    Returns:
        Количество знаков после запятой (2, 4, 6 или 8)
    """
    if price >= 1:
        return 2
    elif price >= 0.01:
        return 4
    elif price >= 0.0001:
        return 6
    else:
        return 8


def format_chart_date(date_obj: datetime, period: str) -> str:
    """
    Форматировать дату для графика.
    ВСЕГДА возвращает время в UTC, но без указания часового пояса в строке.
    """
    from datetime import timezone
    
    # 1. Гарантируем, что datetime в UTC
    if date_obj.tzinfo is None:
        # Если datetime без часового пояса - считаем что это уже UTC
        date_obj_utc = date_obj.replace(tzinfo=timezone.utc)
    else:
        # Если есть часовой пояс - конвертируем в UTC
        date_obj_utc = date_obj.astimezone(timezone.utc)
    
    # 2. Убираем информацию о часовом поясе для обратной совместимости
    date_obj_naive = date_obj_utc.replace(tzinfo=None)
    
    # 3. Форматируем как раньше
    if period in ("1d", "7d"):
        return date_obj_naive.strftime("%Y-%m-%d %H:%M")
    else:
        return date_obj_naive.strftime("%Y-%m-%d 00:00")

