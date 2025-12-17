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
    Возвращает ISO строку с часовым поясом UTC для корректного парсинга на фронтенде.
    Пример: "2025-12-17T18:12:12+00:00"
    """
    from datetime import timezone, datetime
    
    # 1. Гарантируем, что datetime в UTC
    if date_obj.tzinfo is None:
        # Если datetime без часового пояса - считаем что это уже UTC
        date_obj_utc = date_obj.replace(tzinfo=timezone.utc)
    else:
        # Если есть часовой пояс - конвертируем в UTC
        date_obj_utc = date_obj.astimezone(timezone.utc)
    
    # 2. Форматируем как ISO строку с часовым поясом UTC
    # Для периодов 1d и 7d включаем время
    if period in ("1d", "7d"):
        # ISO формат с часовым поясом: "2025-12-17T18:12:12+00:00"
        return date_obj_utc.isoformat()
    else:
        # Для длинных периодов используем только дату с временем 00:00
        date_only = date_obj_utc.date()
        # Создаем datetime с временем 00:00:00 в UTC
        date_with_time = datetime.combine(date_only, datetime.min.time(), tzinfo=timezone.utc)
        return date_with_time.isoformat()

