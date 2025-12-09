"""
Скрипт для очистки кэша списка монет в Redis.
Использование: python scripts/clear_coins_cache.py
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.redis_client import get_redis


async def clear_coins_cache():
    """Очистить кэш списка монет"""
    redis = await get_redis()
    
    if not redis:
        print("❌ Redis недоступен. Убедитесь, что Redis запущен.")
        return
    
    try:
        cache_key = "coins_list:filtered"
        cache_hash_key = "coins_list:config_hash"
        
        # Удаляем кэш данных и хеш
        deleted_data = await redis.delete(cache_key)
        deleted_hash = await redis.delete(cache_hash_key)
        
        if deleted_data or deleted_hash:
            print("✅ Кэш списка монет успешно очищен!")
            print(f"   - Удален ключ: {cache_key}")
            print(f"   - Удален ключ: {cache_hash_key}")
        else:
            print("ℹ️  Кэш уже был пуст или не существует.")
            
    except Exception as e:
        print(f"❌ Ошибка при очистке кэша: {e}")


if __name__ == "__main__":
    asyncio.run(clear_coins_cache())

