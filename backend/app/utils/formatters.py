"""
Утилиты для форматирования данных
"""
from typing import Union


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

