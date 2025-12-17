"""
Утилита для обработки обновлений цен из WebSocket сообщений

"""
import json
import asyncio
import logging
from typing import Dict, Optional, Callable, Tuple
from app.core.redis_client import get_redis
from app.core.coin_registry import coin_registry
from app.utils.formatters import get_price_decimals

logger = logging.getLogger(f"UtilsWebsocketPriceHandler")

async def process_price_update(
    ticker: Dict,
    source: str,
    symbol_extractor: Callable[[Dict], Optional[str]],
    price_extractor: Callable[[Dict], float],
    price_change_extractor: Callable[[Dict], float],
    volume_extractor: Callable[[Dict], float],
    adapter_name: str,
    tracked_coins: set,
    last_update_time: Dict[str, float],
    coins_with_updates: set,
    redis,
) -> Tuple[str, Optional[str]]:
    """
    Обработать обновление цены из WebSocket тикера
    
    Args:
        ticker: Словарь с данными тикера от биржи
        source: 
        symbol_extractor: Функция для извлечения символа из тикера
        price_extractor: Функция для извлечения цены из тикера
        price_change_extractor: Функция для извлечения изменения цены из тикера
        volume_extractor: Функция для извлечения объема из тикера
        adapter_name: Имя адаптера для логирования
        tracked_coins: Множество отслеживаемых монет
        last_update_time: Словарь для отслеживания времени обновлений
        coins_with_updates: Множество монет с обновлениями
        redis: Redis клиент
        
    Returns:
        Tuple (status: str, coin_id: Optional[str])
        status - "updated", "skipped_not_in_map", "skipped_not_tracked", 
                 "skipped_wrong_priority", "skipped_zero_price", "error"
        coin_id - внутренний ID монеты или None
    """
    # Извлекаем символ из тикера
    symbol = symbol_extractor(ticker)
    if not symbol:
        return "skipped_no_symbol", None
    
    # Находим монету в реестре
    coin = coin_registry.find_coin_by_external_id(source, symbol)
    if not coin:
        return "skipped_not_in_map", None
    
    coin_id = coin.id
    
    # Проверяем, отслеживаем ли мы эту монету
    if coin_id not in tracked_coins:
        return "skipped_not_tracked", coin_id
    
    # Проверяем price_priority: источник должен быть первым приоритетом
    price_priority = coin.price_priority
    if not price_priority or price_priority[0] != source:
        return "skipped_wrong_priority", coin_id
    
    # Извлекаем данные из тикера
    price = price_extractor(ticker)
    if price <= 0:
        return "skipped_zero_price", coin_id
    
    price_change_24h = price_change_extractor(ticker)
    volume_24h = volume_extractor(ticker)
    
    # Формируем данные для кэша
    price_data = {
        "price": price,
        "percent_change_24h": price_change_24h,
        "volume_24h": volume_24h,
        "priceDecimals": get_price_decimals(price),
    }
    
    # Записываем в Redis
    if not redis:
        return "error", coin_id
    
    try:
        price_cache_key = f"coin_price:{coin_id}"
        await redis.setex(
            price_cache_key,
            60,  # TTL в секундах
            json.dumps(price_data)
        )
        
        # Обновляем статистику
        current_time = asyncio.get_event_loop().time()
        last_update_time[coin_id] = current_time
        coins_with_updates.add(coin_id)
        
        return "updated", coin_id
        
    except Exception as e:
        logger.error(f"Ошибка записи в Redis для {coin_id}: {e}")
        return "error", coin_id

