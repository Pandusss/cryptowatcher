"""
Скрипт для полной очистки кэша монет в Redis
Очищает статику и цены для всех монет
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.redis_client import get_redis
from app.core.coin_registry import coin_registry


async def clear_all_coins_cache():
    """Очистить весь кэш монет"""
    redis = await get_redis()
    
    if not redis:
        print("❌ Redis недоступен. Убедитесь, что Redis запущен.")
        return
    
    try:
        # Получаем все монеты из конфига
        coin_ids = coin_registry.get_coin_ids(enabled_only=False)
        print(f"Найдено {len(coin_ids)} монет в конфиге")
        
        deleted_static = 0
        deleted_prices = 0
        
        # Очищаем кэш для каждой монеты
        for coin_id in coin_ids:
            # Статика
            static_key = f"coin_static:{coin_id}"
            if await redis.exists(static_key):
                await redis.delete(static_key)
                deleted_static += 1
            
            # Цены
            price_key = f"coin_price:{coin_id}"
            if await redis.exists(price_key):
                await redis.delete(price_key)
                deleted_prices += 1
        
        print(f"\n✅ Кэш очищен:")
        print(f"   - Удалено статики: {deleted_static}")
        print(f"   - Удалено цен: {deleted_prices}")
        
        # Также очищаем общий кэш списка
        cache_key = "coins_list:filtered"
        cache_hash_key = "coins_list:config_hash"
        await redis.delete(cache_key)
        await redis.delete(cache_hash_key)
        print(f"   - Удален общий кэш списка")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке кэша: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(clear_all_coins_cache())

