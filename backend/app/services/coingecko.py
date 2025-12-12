"""
Сервис для работы с CoinGecko API и кэшированием данных о криптовалютах

Архитектура:
- CoinGeckoClient: HTTP клиент для CoinGecko API запросов
- CoinCacheManager: управление кэшем в Redis  
- CoinService: бизнес-логика работы с монетами (использует CoinGecko ТОЛЬКО для статики и изображений)

Примечания:
- CoinGecko используется ТОЛЬКО для статических данных (id, name, symbol, imageUrl)
- Цены получаются из Binance/OKX WebSocket (binance_websocket.py, okx_websocket.py)
- Графики получаются из Binance/OKX (binance_chart.py, okx_chart.py)
"""
import hashlib
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
import httpx

from app.core.config import settings
from app.core.redis_client import get_redis
from app.providers.coingecko_client import CoinGeckoClient
from app.utils.cache import CoinCacheManager
from app.utils.formatters import get_price_decimals
from functools import wraps


# ============================================================================
# Декораторы для кэширования
# ============================================================================

def cached_async(cache_key_func, ttl: int, serialize_func=None, deserialize_func=None):

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Генерируем ключ кэша из аргументов функции
            cache_key = cache_key_func(*args, **kwargs)
            
            # Проверяем кэш
            redis = await get_redis()
            if redis:
                try:
                    cached_data = await redis.get(cache_key)
                    if cached_data:
                        # Десериализуем данные из кэша
                        if deserialize_func:
                            result = deserialize_func(cached_data)
                            print(f"[cached_async] ✅ Данные из кэша для ключа: {cache_key}")
                            return result
                        else:
                            # По умолчанию пытаемся JSON, если не строка - возвращаем как есть
                            if isinstance(cached_data, bytes):
                                cached_data = cached_data.decode('utf-8')
                            try:
                                result = json.loads(cached_data)
                                print(f"[cached_async] ✅ Данные из кэша (JSON) для ключа: {cache_key}")
                                return result
                            except (json.JSONDecodeError, TypeError):
                                print(f"[cached_async] ✅ Данные из кэша (строка) для ключа: {cache_key}")
                                return cached_data
                except Exception as e:
                    print(f"[cached_async] Ошибка чтения из кэша для {cache_key}: {e}")
            
            # Если данных нет в кэше, выполняем функцию
            result = await func(*args, **kwargs)
            
            # Сохраняем результат в кэш
            if redis and result is not None:
                try:
                    # Сериализуем данные перед сохранением
                    if serialize_func:
                        serialized_data = serialize_func(result)
                    else:
                        # По умолчанию JSON для словарей и списков, иначе строка
                        if isinstance(result, (dict, list)):
                            serialized_data = json.dumps(result)
                        else:
                            serialized_data = str(result)
                    
                    await redis.setex(cache_key, ttl, serialized_data)
                    print(f"[cached_async] 💾 Данные сохранены в кэш для ключа: {cache_key} (TTL: {ttl} сек)")
                except Exception as e:
                    print(f"[cached_async] Ошибка записи в кэш для {cache_key}: {e}")
            
            return result
        
        return wrapper
    return decorator


class CoinService:
    
    def __init__(self):
        self.client = CoinGeckoClient()  # Только для CoinGecko API
        self.cache = CoinCacheManager()   # Кэш в Redis
    
    async def close(self):
        await self.client.close()
    
    
    def _load_coins_config(self) -> tuple[List[str], str]:
        try:
            from app.core.coin_registry import coin_registry
            
            # Получаем все включенные монеты из реестра (автоматически перезагрузит конфиг при изменении)
            coin_ids = coin_registry.get_coin_ids(enabled_only=True)
            
            # Используем хеш всего конфига из CoinRegistry (учитывает все изменения, включая содержимое монет)
            config_hash = coin_registry.get_config_hash() or hashlib.md5(','.join(coin_ids).encode()).hexdigest()
            
            print(f"[CoinService] Загружено {len(coin_ids)} монет из CoinRegistry (хеш: {config_hash[:8]}...)")
            return coin_ids, config_hash
        except Exception as e:
            print(f"[CoinService] Ошибка загрузки монет из CoinRegistry: {e}")
            import traceback
            print(f"[CoinService] Traceback: {traceback.format_exc()}")
            return [], ""
    
    def _format_coin_data(self, coin_data: Dict, coin_id: str) -> Dict:
        
        price = coin_data.get("current_price", 0)
        
        return {
            "id": coin_id,  # Всегда используем внутренний ID из конфига
            "name": coin_data.get("name", ""),
            "symbol": coin_data.get("symbol", "").upper(),
            "slug": coin_id,  # Используем внутренний ID для slug
            "imageUrl": coin_data.get("image", ""),
            "quote": {
                "USD": {
                    "price": price,
                    "percent_change_24h": coin_data.get("price_change_percentage_24h", 0),
                    "volume_24h": coin_data.get("total_volume", 0),
                }
            },
            "priceDecimals": get_price_decimals(price),
        }
    
    async def get_crypto_list_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Получить цены для списка монет ТОЛЬКО из Redis (обновляются через Binance/OKX WebSocket).
        CoinGecko НЕ используется для цен - только для статики (картинки, названия).
        """
        if not coin_ids:
            return {}
        
        print(f"\n[CoinService.get_crypto_list_prices] Загружаем цены для {len(coin_ids)} монет из Redis...")
        
        # Читаем цены ТОЛЬКО из Redis кэша (обновляется через Binance/OKX WebSocket)
        prices_dict = {}
        redis = await get_redis()
        
        if redis:
            # Читаем все цены параллельно из Redis
            import asyncio
            tasks = []
            for coin_id in coin_ids:
                tasks.append(self.cache.get_price(coin_id))
            
            cached_prices = await asyncio.gather(*tasks, return_exceptions=True)
            
            for coin_id, cached_price in zip(coin_ids, cached_prices):
                if isinstance(cached_price, Exception):
                    print(f"[CoinService.get_crypto_list_prices] Ошибка чтения цены для {coin_id}: {cached_price}")
                    continue
                    
                if cached_price and cached_price.get("price", 0) > 0:
                    prices_dict[coin_id] = {
                        "price": cached_price.get("price", 0),
                        "percent_change_24h": cached_price.get("percent_change_24h", 0),
                        "volume_24h": cached_price.get("volume_24h", 0),
                        "priceDecimals": cached_price.get("priceDecimals", get_price_decimals(cached_price.get("price", 0))),
                    }
        else:
            print("[CoinService.get_crypto_list_prices] ⚠️ Redis недоступен, цены недоступны (CoinGecko НЕ используется для цен)")
            # НЕ используем CoinGecko как fallback - цены должны приходить только из WebSocket
        
        print(f"[CoinService.get_crypto_list_prices] Получено цен: {len(prices_dict)} из {len(coin_ids)} запрошенных")
        return prices_dict
    
    async def get_crypto_list(
        self,
        limit: int = 100,
        page: int = 1,
        force_refresh: bool = False,
    ) -> List[Dict]:
        
        config_coins, config_hash = self._load_coins_config()
        
        if not config_coins:
            print("[CoinService.get_crypto_list] Конфиг-файл пустой, возвращаем пустой список")
            return []
        
        # Проверяем, изменился ли конфиг (по хешу)
        redis = await get_redis()
        if redis:
            cached_hash_key = "coins_list:config_hash"
            cached_hash_raw = await redis.get(cached_hash_key)
            
            # Обрабатываем данные из Redis (могут быть bytes или str)
            cached_hash = None
            if cached_hash_raw:
                if isinstance(cached_hash_raw, bytes):
                    cached_hash = cached_hash_raw.decode('utf-8')
                else:
                    cached_hash = str(cached_hash_raw)
            
            if cached_hash and cached_hash != config_hash:
                print(f"[CoinService.get_crypto_list] 🔄 Обнаружено изменение конфига (хеш: {cached_hash[:8]}... -> {config_hash[:8]}...)")
                print(f"[CoinService.get_crypto_list] Очищаем кэш списка монет и статики...")
                # Очищаем кэш списка монет
                await redis.delete("coins_list:filtered")
                # Очищаем кэш статики для всех монет (чтобы изменения отразились)
                # Используем паттерн для удаления всех ключей coin_static:*
                try:
                    keys_to_delete = []
                    async for key in redis.scan_iter(match="coin_static:*"):
                        keys_to_delete.append(key)
                    if keys_to_delete:
                        await redis.delete(*keys_to_delete)
                        print(f"[CoinService.get_crypto_list]   - Удалено {len(keys_to_delete)} ключей статики из кэша")
                except Exception as e:
                    print(f"[CoinService.get_crypto_list] ⚠️ Ошибка при очистке кэша статики: {e}")
                # Обновляем хеш
                await redis.set(cached_hash_key, config_hash)
            elif not cached_hash:
                # Первый запуск - сохраняем хеш
                await redis.set(cached_hash_key, config_hash)
        
        print(f"\n[CoinService.get_crypto_list] ===== НАЧАЛО ОБРАБОТКИ =====")
        print(f"[CoinService.get_crypto_list] Всего монет в конфиге: {len(config_coins)}")
        print(f"[CoinService.get_crypto_list] Проверяем кэш для каждой монеты...")
        
        formatted_coins = []
        coins_to_fetch = []
        coins_with_full_cache = 0
        coins_with_static_only = 0
        coins_with_no_cache = 0
        
        # Оптимизированная проверка кэша через Redis pipeline (batch запрос)
        if not force_refresh:
            try:
                # Получаем все данные одним batch запросом через pipeline
                cached_data = await self.cache.get_static_and_prices_batch(config_coins)
                
                # Обрабатываем результаты
                for coin_id in config_coins:
                    cached_coin = None
                    coin_cache = cached_data.get(coin_id, {"static": None, "price": None})
                    cached_static = coin_cache.get("static")
                    cached_price = coin_cache.get("price")
                    
                    if cached_static:
                        cached_coin = cached_static.copy()
                        
                        # Убеждаемся, что ID правильный (внутренний, а не CoinGecko)
                        cached_coin["id"] = coin_id
                        cached_coin["slug"] = coin_id
                        
                        if cached_price:
                            cached_coin["quote"] = {
                                "USD": {
                                    "price": cached_price.get("price", 0),
                                    "percent_change_24h": cached_price.get("percent_change_24h", 0),
                                    "volume_24h": cached_price.get("volume_24h", 0),
                                }
                            }
                            cached_coin["priceDecimals"] = cached_price.get("priceDecimals", 2)
                            coins_with_full_cache += 1
                        else:
                            cached_coin["quote"] = {"USD": {"price": 0, "percent_change_24h": 0, "volume_24h": 0}}
                            cached_coin["priceDecimals"] = 2
                            coins_with_static_only += 1
                        
                        if "priceDecimals" not in cached_coin:
                            price = cached_coin.get("quote", {}).get("USD", {}).get("price", 0)
                            cached_coin["priceDecimals"] = get_price_decimals(price)
                    
                    if cached_coin:
                        formatted_coins.append(cached_coin)
                    else:
                        coins_with_no_cache += 1
                        coins_to_fetch.append(coin_id)
                        
            except Exception as e:
                print(f"[CoinService.get_crypto_list] Ошибка при batch чтении кэша: {e}")
                # В случае ошибки добавляем все монеты в список для загрузки
                coins_to_fetch = config_coins.copy()
                coins_with_no_cache = len(config_coins)
        else:
            # Если force_refresh, все монеты нужно загрузить заново
            coins_to_fetch = config_coins.copy()
            coins_with_no_cache = len(config_coins)
        
        print(f"[CoinService.get_crypto_list] === РЕЗУЛЬТАТЫ ПРОВЕРКИ КЭША ===")
        print(f"[CoinService.get_crypto_list] Полностью в кэше (статика + цены): {coins_with_full_cache}")
        print(f"[CoinService.get_crypto_list] Только статика в кэше: {coins_with_static_only}")
        print(f"[CoinService.get_crypto_list] Нет в кэше: {coins_with_no_cache}")
        print(f"[CoinService.get_crypto_list] ⚠️ Цены берутся ТОЛЬКО из кэша Redis (обновляются каждые 10 сек)")
        
        # Если все в кэше, возвращаем немедленно
        if formatted_coins and not coins_to_fetch:
            coin_order = {coin_id: idx for idx, coin_id in enumerate(config_coins)}
            formatted_coins.sort(key=lambda x: coin_order.get(x.get("id"), 9999))
            print(f"[CoinService.get_crypto_list] ✅ Все {len(formatted_coins)} монет из кэша, возвращаем немедленно")
            return formatted_coins
        
        # Загружаем статические данные для монет, которых нет в кэше
        if coins_to_fetch:
            print(f"\n[CoinService.get_crypto_list] === ЗАГРУЗКА СТАТИЧЕСКИХ ДАННЫХ ===")
            print(f"[CoinService.get_crypto_list] Монет для загрузки: {len(coins_to_fetch)}")
            
            try:
                # Преобразуем внутренние ID в CoinGecko ID
                from app.core.coin_registry import coin_registry
                
                coingecko_ids = []
                coingecko_to_internal = {}  # coingecko_id -> internal_id
                
                for internal_id in coins_to_fetch:
                    coin = coin_registry.get_coin(internal_id)
                    if coin:
                        coingecko_id = coin.external_ids.get("coingecko")
                        if coingecko_id:
                            coingecko_ids.append(coingecko_id)
                            coingecko_to_internal[coingecko_id] = internal_id
                        else:
                            print(f"[CoinService.get_crypto_list] ⚠️ Монета {internal_id} не имеет CoinGecko ID в external_ids.coingecko")
                    else:
                        print(f"[CoinService.get_crypto_list] ⚠️ Монета {internal_id} не найдена в реестре")
                
                if not coingecko_ids:
                    print(f"[CoinService.get_crypto_list] ⚠️ Нет CoinGecko ID для загрузки")
                    coins_dict = {}
                else:
                    ids_param = ','.join(coingecko_ids)
                    print(f"[CoinService.get_crypto_list] Отправляем запрос к /coins/markets с CoinGecko ID: {ids_param[:100]}...")
                    coins_data = await self.client.get(
                        "/coins/markets",
                        params={
                            "vs_currency": "usd",
                            "ids": ids_param,
                            "order": "market_cap_desc",
                            "per_page": len(coingecko_ids),
                            "sparkline": False,
                        },
                    )
                    
                    # Создаем словарь: internal_id -> coin_data
                    coins_dict = {}
                    for coin_data in coins_data:
                        coingecko_id = coin_data.get("id")
                        if coingecko_id in coingecko_to_internal:
                            internal_id = coingecko_to_internal[coingecko_id]
                            coins_dict[internal_id] = coin_data
                    
                    print(f"[CoinService.get_crypto_list] Получено статических данных: {len(coins_dict)} из {len(coins_to_fetch)}")
                
            except Exception as e:
                print(f"[CoinService.get_crypto_list] Ошибка при получении статических данных: {e}")
                import traceback
                print(f"[CoinService.get_crypto_list] Traceback: {traceback.format_exc()}")
                coins_dict = {}
            
            # Обрабатываем загруженные данные
            saved_static_count = 0
            for coin_id in coins_to_fetch:
                if coin_id in coins_dict:
                    coin_data = coins_dict[coin_id]
                    formatted_coin = self._format_coin_data(coin_data, coin_id)
                    
                    # Проверяем цену в кэше
                    cached_price = await self.cache.get_price(coin_id)
                    
                    if cached_price:
                        formatted_coin["quote"] = {
                            "USD": {
                                "price": cached_price.get("price", 0),
                                "percent_change_24h": cached_price.get("percent_change_24h", 0),
                                "volume_24h": cached_price.get("volume_24h", 0),
                            }
                        }
                        formatted_coin["priceDecimals"] = cached_price.get("priceDecimals", get_price_decimals(cached_price.get("price", 0)))
                    else:
                        formatted_coin["quote"] = {"USD": {"price": 0, "percent_change_24h": 0, "volume_24h": 0}}
                        formatted_coin["priceDecimals"] = 2
                    
                    formatted_coins.append(formatted_coin)
                    
                    # Сохраняем ТОЛЬКО статику (цены обновляются в фоне)
                    static_data = {
                        "id": formatted_coin.get("id"),
                        "name": formatted_coin.get("name"),
                        "symbol": formatted_coin.get("symbol"),
                        "slug": formatted_coin.get("slug"),
                        "imageUrl": formatted_coin.get("imageUrl"),
                    }
                    await self.cache.set_static(coin_id, static_data)
                    saved_static_count += 1
                else:
                    print(f"[CoinService.get_crypto_list] ⚠️ Монета {coin_id} не найдена в ответе API")
            
            print(f"[CoinService.get_crypto_list] Сохранено статических данных в кэш: {saved_static_count}")
        
        # Сортируем по порядку из конфига
        coin_order = {coin_id: idx for idx, coin_id in enumerate(config_coins)}
        formatted_coins.sort(key=lambda x: coin_order.get(x.get("id"), 9999))
        
        print(f"\n[CoinService.get_crypto_list] === ИТОГОВЫЕ РЕЗУЛЬТАТЫ ===")
        print(f"[CoinService.get_crypto_list] Итого отформатировано монет: {len(formatted_coins)}")
        print(f"[CoinService.get_crypto_list] Ожидалось монет из конфига: {len(config_coins)}")
        if formatted_coins:
            first_coin_price = formatted_coins[0].get('quote', {}).get('USD', {}).get('price', 0)
            print(f"[CoinService.get_crypto_list] Первая монета: {formatted_coins[0].get('name')} (${first_coin_price})")
        print(f"[CoinService.get_crypto_list] ===== КОНЕЦ ОБРАБОТКИ =====\n")
        
        return formatted_coins
    
    async def get_crypto_details(self, coin_id: str) -> Dict:
        
        # Сначала получаем статические данные (из кэша или API)
        cached_static = await self.cache.get_static(coin_id)
        
        cached_price = await self.cache.get_price(coin_id)
        if cached_price:
            print(f"[CoinService.get_crypto_details] ✅ Цена {coin_id} из кэша Redis: ${cached_price.get('price', 0)}")
        
        # Если есть статика и цена в кэше - возвращаем сразу
        if cached_static and cached_price:
            coin = {
                "id": cached_static.get("id", coin_id),
                "name": cached_static.get("name", ""),
                "symbol": cached_static.get("symbol", "").upper(),
                "currentPrice": cached_price.get("price", 0),
                "priceChange24h": cached_price.get("volume_24h", 0),
                "priceChangePercent24h": cached_price.get("percent_change_24h", 0),
                "imageUrl": cached_static.get("imageUrl", ""),
                "priceDecimals": cached_price.get("priceDecimals", get_price_decimals(cached_price.get("price", 0))),
            }
            print(f"[CoinService.get_crypto_details] ✅ Все данные из кэша Redis")
            return coin
        
        # Если статики нет в кэше, загружаем из API
        if not cached_static:
            data = await self.client.get(
                f"/coins/{coin_id}",
                params={
                    "localization": False,
                    "tickers": False,
                    "market_data": False,
                    "community_data": False,
                    "developer_data": False,
                    "sparkline": False,
                },
            )
            
            image_url = data.get("image", {}).get("large") or data.get("image", {}).get("small")
            
            # Сохраняем статику в кэш
            static_data = {
                "id": data.get("id", coin_id),
                "name": data.get("name", ""),
                "symbol": data.get("symbol", "").upper(),
                "imageUrl": image_url,
            }
            await self.cache.set_static(coin_id, static_data)
            
            # Сохраняем иконку отдельно
            if image_url:
                await self.cache.set_image_url(coin_id, image_url)
            
            cached_static = static_data
        
        # Используем цену из кэша (если есть), иначе 0 (обновится через 10 секунд)
        price = cached_price.get("price", 0) if cached_price else 0
        price_change_24h = cached_price.get("percent_change_24h", 0) if cached_price else 0
        price_decimals = cached_price.get("priceDecimals", get_price_decimals(price)) if cached_price else get_price_decimals(price)
        
        coin = {
            "id": cached_static.get("id", coin_id),
            "name": cached_static.get("name", ""),
            "symbol": cached_static.get("symbol", "").upper(),
            "currentPrice": price,
            "priceChange24h": cached_price.get("volume_24h", 0) if cached_price else 0,
            "priceChangePercent24h": price_change_24h,
            "imageUrl": cached_static.get("imageUrl", ""),
            "priceDecimals": price_decimals,
        }
        
        return coin
    
    @cached_async(
        lambda self, coin_id: CoinCacheManager._get_image_url_key(coin_id),
        ttl=CoinCacheManager.CACHE_TTL_IMAGE_URL,
        serialize_func=lambda x: x if isinstance(x, str) else str(x),  # Сохраняем строку как есть
        deserialize_func=lambda x: x.decode('utf-8') if isinstance(x, bytes) else x
    )
    async def _fetch_coin_image_url(self, coin_id: str) -> Optional[str]:

        try:
            data = await self.client.get(
                f"/coins/{coin_id}",
                params={
                    "localization": False,
                    "tickers": False,
                    "market_data": False,
                    "community_data": False,
                    "developer_data": False,
                    "sparkline": False,
                },
            )
            
            image_url = data.get("image", {}).get("large") or data.get("image", {}).get("small")
            
            if image_url:
                print(f"[CoinService._fetch_coin_image_url] ✅ URL изображения {coin_id} загружен из API")
                return image_url
            else:
                print(f"[CoinService._fetch_coin_image_url] ⚠️ URL изображения не найден для {coin_id}")
                return None
        except Exception as e:
            print(f"[CoinService._fetch_coin_image_url] Ошибка при получении URL изображения для {coin_id}: {e}")
            return None
    
    async def get_coin_image_url(self, coin_id: str) -> Optional[str]:
        
        return await self._fetch_coin_image_url(coin_id)
    
    async def get_crypto_chart(
        self,
        coin_id: str,
        period: str = "7d",  # 1d, 7d, 30d, 1y
    ) -> List[Dict]:

        cached_data = await self.cache.get_chart(coin_id, period)
        if cached_data:
            print(f"[CoinService.get_crypto_chart] ✅ Данные из кэша для {coin_id} ({period})")
            return cached_data
        
        from app.providers.binance_chart import binance_chart_adapter
        from app.core.coin_registry import coin_registry
        
        binance_symbol = coin_registry.get_external_id(coin_id, "binance")
        
        if binance_symbol:
            binance_data = await binance_chart_adapter.get_chart_data(binance_symbol, period)
            if binance_data:
                await self.cache.set_chart(coin_id, period, binance_data)
                print(f"[CoinService.get_crypto_chart] ✅ Использованы данные из Binance для {coin_id} ({period})")
                return binance_data
        
        # Если Binance недоступен, возвращаем пустой список
        print(f"[CoinService.get_crypto_chart] Монета {coin_id} не найдена в Binance, график недоступен")
        return []
