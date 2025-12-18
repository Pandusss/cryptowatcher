"""
Utility for processing price updates from WebSocket messages

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
    Process price update from WebSocket ticker
    
    Args:
        ticker: Dictionary with ticker data from exchange
        source: 
        symbol_extractor: Function to extract symbol from ticker
        price_extractor: Function to extract price from ticker
        price_change_extractor: Function to extract price change from ticker
        volume_extractor: Function to extract volume from ticker
        adapter_name: Adapter name for logging
        tracked_coins: Set of tracked coins
        last_update_time: Dictionary for tracking update times
        coins_with_updates: Set of coins with updates
        redis: Redis client
        
    Returns:
        Tuple (status: str, coin_id: Optional[str])
        status - "updated", "skipped_not_in_map", "skipped_not_tracked", 
                 "skipped_wrong_priority", "skipped_zero_price", "error"
        coin_id - internal coin ID or None
    """
    # Extract symbol from ticker
    symbol = symbol_extractor(ticker)
    if not symbol:
        return "skipped_no_symbol", None
    
    # Find coin in registry
    coin = coin_registry.find_coin_by_external_id(source, symbol)
    if not coin:
        return "skipped_not_in_map", None
    
    coin_id = coin.id
    
    # Check if we're tracking this coin
    if coin_id not in tracked_coins:
        return "skipped_not_tracked", coin_id
    
    # Check price_priority: source must be first priority
    price_priority = coin.price_priority
    if not price_priority or price_priority[0] != source:
        return "skipped_wrong_priority", coin_id
    
    # Extract data from ticker
    price = price_extractor(ticker)
    if price <= 0:
        return "skipped_zero_price", coin_id
    
    price_change_24h = price_change_extractor(ticker)
    volume_24h = volume_extractor(ticker)
    
    # Form data for cache
    price_data = {
        "price": price,
        "percent_change_24h": price_change_24h,
        "volume_24h": volume_24h,
        "priceDecimals": get_price_decimals(price),
    }
    
    # Write to Redis
    if not redis:
        return "error", coin_id
    
    try:
        price_cache_key = f"coin_price:{coin_id}"
        await redis.setex(
            price_cache_key,
            86400,  # TTL 24 hours - price persists until overwritten
            json.dumps(price_data)
        )
        
        # Update statistics
        current_time = asyncio.get_event_loop().time()
        last_update_time[coin_id] = current_time
        coins_with_updates.add(coin_id)
        
        return "updated", coin_id
        
    except Exception as e:
        logger.error(f"Redis write error for {coin_id}: {e}")
        return "error", coin_id