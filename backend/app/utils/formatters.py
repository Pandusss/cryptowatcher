"""
Утилиты для форматирования данных
"""
from typing import Union
from datetime import datetime


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
    Форматировать дату для графика в зависимости от периода
    
    Args:
        date_obj: Объект datetime
        period: Период графика ("1d", "7d", "30d", "1y")
        
    Returns:
        Отформатированная строка даты
    """
    if period in ("1d", "7d"):
        # Для коротких периодов показываем дату и время
        return date_obj.strftime("%Y-%m-%d %H:%M")
    else:
        # Для длинных периодов показываем только дату (время 00:00)
        return date_obj.strftime("%Y-%m-%d 00:00")

