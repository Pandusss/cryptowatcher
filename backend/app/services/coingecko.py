"""
Сервис для работы с CoinGecko API и кэшированием данных о криптовалютах

Архитектура:
- CoinGeckoClient: HTTP клиент для CoinGecko API запросов
- CoinCacheManager: управление кэшем в Redis  
- CoinService: бизнес-логика работы с монетами (использует CoinGecko для статики и изображений)
- BinanceService: для графиков (используется через CoinService)

Примечание: Цены получаются из Binance WebSocket (binance_websocket.py)
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
from functools import wraps


# ============================================================================
# Декораторы для кэширования
# ============================================================================

def cached_async(cache_key_func, ttl: int, serialize_func=None, deserialize_func=None):
    """
    Декоратор для автоматического кэширования результатов async функций
    
    Что такое декоратор?
    Декоратор - это функция, которая принимает другую функцию и расширяет её поведение.
    Вместо изменения самой функции, мы "оборачиваем" её декоратором.
    
    Пример использования:
    @cached_async(lambda coin_id: f"coin_price:{coin_id}", ttl=10)
    async def get_price(coin_id: str):
        # код функции
        return price_data
    
    Как это работает:
    1. При вызове get_price(coin_id) сначала проверяется кэш
    2. Если данные в кэше - возвращаются из кэша
    3. Если данных нет - выполняется функция и результат сохраняется в кэш
    
    Args:
        cache_key_func: Функция для генерации ключа кэша из аргументов
        ttl: Время жизни кэша в секундах
        serialize_func: Функция для сериализации данных перед сохранением (по умолчанию json.dumps)
        deserialize_func: Функция для десериализации данных из кэша (по умолчанию json.loads)
    """
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


# ============================================================================
# CoinGeckoClient и CoinCacheManager теперь находятся в:
# - CoinGeckoClient: app.providers.static.coingecko.client
# - CoinCacheManager: app.utils.cache
# ============================================================================
# Импортируем из новых мест для обратной совместимости
# ============================================================================


# ============================================================================
# CoinService - бизнес-логика работы с монетами
# ============================================================================

class CoinService:
    """
    Сервис для работы с данными криптовалют.
    
    Использует:
    - CoinGecko API: для статических данных (id, name, symbol, imageUrl)
    - Binance WebSocket: для цен (через Redis кэш, обновляется в binance_websocket.py)
    - BinanceService: для графиков (с fallback на CoinGecko)
    """
    
    BATCH_PRICE_SIZE = 100  # Максимум монет в одном batch запросе
    
    def __init__(self):
        self.client = CoinGeckoClient()  # Только для CoinGecko API
        self.cache = CoinCacheManager()   # Кэш в Redis
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.close()
    
    @staticmethod
    def get_price_decimals(price: float) -> int:
        """Определить количество знаков после запятой для цены"""
        if price >= 1:
            return 2
        elif price >= 0.01:
            return 4
        elif price >= 0.0001:
            return 6
        else:
            return 8
    
    def _load_coins_config(self) -> tuple[List[str], str]:
        """Загрузить список монет из CoinRegistry"""
        try:
            from app.core.coin_registry import coin_registry
            
            # Получаем все включенные монеты из реестра
            coin_ids = coin_registry.get_coin_ids(enabled_only=True)
            
            # Вычисляем хеш для проверки изменений (используем количество монет как простой хеш)
            config_hash = hashlib.md5(str(len(coin_ids)).encode()).hexdigest()
            
            print(f"[CoinService] Загружено {len(coin_ids)} монет из CoinRegistry (хеш: {config_hash[:8]}...)")
            return coin_ids, config_hash
        except Exception as e:
            print(f"[CoinService] Ошибка загрузки монет из CoinRegistry: {e}")
            import traceback
            print(f"[CoinService] Traceback: {traceback.format_exc()}")
            return [], ""
    
    def _format_coin_data(self, coin_data: Dict, coin_id: str) -> Dict:
        """Форматировать данные монеты для фронтенда"""
        price = coin_data.get("current_price", 0)
        
        return {
            "id": coin_data.get("id", coin_id),
            "name": coin_data.get("name", ""),
            "symbol": coin_data.get("symbol", "").upper(),
            "slug": coin_data.get("id", coin_id),
            "imageUrl": coin_data.get("image", ""),
            "quote": {
                "USD": {
                    "price": price,
                    "percent_change_24h": coin_data.get("price_change_percentage_24h", 0),
                    "volume_24h": coin_data.get("total_volume", 0),
                }
            },
            "priceDecimals": self.get_price_decimals(price),
        }
    
    async def _fetch_single_batch_prices(self, batch: List[str], batch_num: int, total_batches: int) -> Dict[str, Dict[str, Any]]:
        """
        Внутренний метод для загрузки цен одного батча.
        Используется для параллельного выполнения через asyncio.gather.
        """
        ids_param = ','.join(batch)
        
        print(f"[CoinService._fetch_single_batch_prices] Батч {batch_num}/{total_batches}: отправляем запрос для {len(batch)} монет...")
        
        try:
            data = await self.client.get(
                "/simple/price",
                params={
                    "ids": ids_param,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_24hr_vol": "true",
                },
            )
            
            batch_prices = {}
            for coin_id, price_data in data.items():
                if price_data and 'usd' in price_data:
                    batch_prices[coin_id] = {
                        'usd': price_data.get('usd', 0),
                        'usd_24h_change': price_data.get('usd_24h_change', 0),
                        'usd_24h_vol': price_data.get('usd_24h_vol', 0),
                    }
            
            print(f"[CoinService._fetch_single_batch_prices] Батч {batch_num}/{total_batches}: получено {len(batch_prices)} цен")
            return batch_prices
            
        except Exception as e:
            print(f"[CoinService._fetch_single_batch_prices] Ошибка батча {batch_num}: {e}")
            return {}
    
    async def get_batch_prices(self, coin_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Получить цены для нескольких монет через batch API.
        Оптимизировано: использует asyncio.gather для параллельных запросов всех батчей.
        """
        if not coin_ids:
            return {}
        
        print(f"[CoinService.get_batch_prices] Запрашиваем цены для {len(coin_ids)} монет...")
        
        try:
            total_batches = (len(coin_ids) + self.BATCH_PRICE_SIZE - 1) // self.BATCH_PRICE_SIZE
            
            if total_batches == 1:
                print(f"[CoinService.get_batch_prices] ✅ ОДИН запрос для всех {len(coin_ids)} монет")
                # Если один батч, выполняем напрямую
                batch = coin_ids[0:self.BATCH_PRICE_SIZE]
                return await self._fetch_single_batch_prices(batch, 1, 1)
            
            print(f"[CoinService.get_batch_prices] Разбиваем на {total_batches} батчей и выполняем ПАРАЛЛЕЛЬНО")
            
            # Создаем список задач для всех батчей
            tasks = []
            for i in range(0, len(coin_ids), self.BATCH_PRICE_SIZE):
                batch = coin_ids[i:i + self.BATCH_PRICE_SIZE]
                batch_num = i // self.BATCH_PRICE_SIZE + 1
                # Создаем задачу для каждого батча (но не выполняем сразу)
                tasks.append(self._fetch_single_batch_prices(batch, batch_num, total_batches))
            
            # Выполняем все батчи ПАРАЛЛЕЛЬНО с помощью asyncio.gather
            # return_exceptions=True позволяет продолжить работу даже если один батч упал
            print(f"[CoinService.get_batch_prices] 🚀 Запускаем {len(tasks)} параллельных запросов...")
            start_time = asyncio.get_event_loop().time()
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            elapsed_time = asyncio.get_event_loop().time() - start_time
            print(f"[CoinService.get_batch_prices] ⚡ Все {len(tasks)} батчей выполнены за {elapsed_time:.2f} секунд (параллельно)")
            
            # Объединяем результаты всех батчей
            all_prices = {}
            successful_batches = 0
            failed_batches = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"[CoinService.get_batch_prices] ❌ Батч {i+1} завершился с ошибкой: {result}")
                    failed_batches += 1
                elif isinstance(result, dict):
                    all_prices.update(result)
                    successful_batches += 1
                else:
                    print(f"[CoinService.get_batch_prices] ⚠️ Батч {i+1} вернул неожиданный тип: {type(result)}")
                    failed_batches += 1
            
            print(f"[CoinService.get_batch_prices] ✅ Успешно: {successful_batches} батчей, ошибок: {failed_batches}")
            print(f"[CoinService.get_batch_prices] Всего получено: {len(all_prices)} цен из {len(coin_ids)} запрошенных")
            
            return all_prices
            
        except Exception as e:
            print(f"[CoinService.get_batch_prices] Критическая ошибка: {e}")
            import traceback
            print(f"[CoinService.get_batch_prices] Traceback: {traceback.format_exc()}")
            return {}
    
    async def get_crypto_list_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """Получить только цены для списка монет"""
        if not coin_ids:
            return {}
        
        print(f"\n[CoinService.get_crypto_list_prices] Загружаем цены для {len(coin_ids)} монет...")
        
        # Получаем цены через batch API
        batch_prices = await self.get_batch_prices(coin_ids)
        
        # Форматируем и сохраняем в кэш
        prices_dict = {}
        for coin_id, price_info in batch_prices.items():
            price = price_info.get('usd', 0)
            if price > 0:
                price_data = {
                    "price": price,
                    "percent_change_24h": price_info.get('usd_24h_change', 0),
                    "volume_24h": price_info.get('usd_24h_vol', 0),
                    "priceDecimals": self.get_price_decimals(price),
                }
                prices_dict[coin_id] = price_data
                
                # Сохраняем в кэш
                await self.cache.set_price(coin_id, price_data)
        
        print(f"[CoinService.get_crypto_list_prices] Получено цен: {len(prices_dict)} из {len(coin_ids)} запрошенных")
        return prices_dict
    
    async def get_crypto_list(
        self,
        limit: int = 100,
        page: int = 1,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """
        Получить список криптовалют из конфиг-файла.
        
        Источники данных:
        - Статика (id, name, symbol, imageUrl): CoinGecko API (/coins/markets)
        - Цены: Redis кэш (обновляется Binance WebSocket)
        """
        config_coins, config_hash = self._load_coins_config()
        
        if not config_coins:
            print("[CoinService.get_crypto_list] Конфиг-файл пустой, возвращаем пустой список")
            return []
        
        print(f"\n[CoinService.get_crypto_list] ===== НАЧАЛО ОБРАБОТКИ =====")
        print(f"[CoinService.get_crypto_list] Всего монет в конфиге: {len(config_coins)}")
        print(f"[CoinService.get_crypto_list] Проверяем кэш для каждой монеты...")
        
        formatted_coins = []
        coins_to_fetch = []
        coins_with_full_cache = 0
        coins_with_static_only = 0
        coins_with_no_cache = 0
        
        # Проверяем кэш для каждой монеты
        for coin_id in config_coins:
            cached_coin = None
            
            if not force_refresh:
                try:
                    cached_static = await self.cache.get_static(coin_id)
                    cached_price = await self.cache.get_price(coin_id)
                    
                    if cached_static:
                        cached_coin = cached_static.copy()
                        
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
                            cached_coin["priceDecimals"] = self.get_price_decimals(price)
                            
                except Exception as e:
                    print(f"[CoinService.get_crypto_list] Ошибка при чтении кэша для {coin_id}: {e}")
            
            if cached_coin:
                formatted_coins.append(cached_coin)
            else:
                coins_with_no_cache += 1
                coins_to_fetch.append(coin_id)
        
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
                ids_param = ','.join(coins_to_fetch)
                print(f"[CoinService.get_crypto_list] Отправляем запрос к /coins/markets...")
                coins_data = await self.client.get(
                    "/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "ids": ids_param,
                        "order": "market_cap_desc",
                        "per_page": len(coins_to_fetch),
                        "sparkline": False,
                    },
                )
                
                coins_dict = {coin_data.get("id"): coin_data for coin_data in coins_data if coin_data.get("id")}
                print(f"[CoinService.get_crypto_list] Получено статических данных: {len(coins_dict)} из {len(coins_to_fetch)}")
                
            except Exception as e:
                print(f"[CoinService.get_crypto_list] Ошибка при получении статических данных: {e}")
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
                        formatted_coin["priceDecimals"] = cached_price.get("priceDecimals", self.get_price_decimals(cached_price.get("price", 0)))
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
        """
        Получить детали криптовалюты.
        
        Источники данных:
        - Статика (id, name, symbol, imageUrl): CoinGecko API или кэш
        - Цены: Redis кэш (обновляется Binance WebSocket)
        """
        # Сначала получаем статические данные (из кэша или API)
        cached_static = await self.cache.get_static(coin_id)
        
        # Получаем цену ИЗ КЭША Redis (обновляется каждые 10 секунд)
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
                "priceDecimals": cached_price.get("priceDecimals", self.get_price_decimals(cached_price.get("price", 0))),
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
        price_decimals = cached_price.get("priceDecimals", self.get_price_decimals(price)) if cached_price else self.get_price_decimals(price)
        
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
        """
        Внутренний метод для загрузки URL изображения из API.
        Кэширование выполняется автоматически через декоратор.
        """
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
        """
        Получить URL изображения монеты из CoinGecko API.
        
        Иконки монет не меняются, поэтому кэшируем на 7 дней.
        Использует декоратор для автоматического кэширования.
        """
        return await self._fetch_coin_image_url(coin_id)
    
    @cached_async(
        lambda self, coin_id, period: CoinCacheManager._get_chart_key(coin_id, period),
        ttl=CoinCacheManager.CACHE_TTL_CHART
    )
    async def _fetch_crypto_chart_data(
        self,
        coin_id: str,
        period: str = "7d",
    ) -> List[Dict]:
        """
        Внутренний метод для загрузки данных графика из API.
        Кэширование выполняется автоматически через декоратор.
        """
        # Маппинг периодов на дни для CoinGecko API
        days_map = {
            "1d": 1,
            "7d": 7,
            "30d": 30,
            "1y": 365,
        }
        days = days_map.get(period, 7)
        
        # Если coin_id - это число (старый CoinMarketCap ID), нужно получить CoinGecko ID
        cg_coin_id = coin_id
        
        # Если coin_id - число, пытаемся получить CoinGecko ID из деталей монеты
        if coin_id.isdigit():
            print(f"[CoinService._fetch_crypto_chart_data] Обнаружен числовой ID, пытаемся получить CoinGecko ID")
            try:
                # Используем маппинг популярных монет
                id_mapping = {
                    "1": "bitcoin",
                    "1027": "ethereum",
                    "825": "tether",
                    "52": "ripple",
                    "11419": "the-open-network",
                    "1958": "tron",
                    "28850": "notcoin",
                    "1839": "binancecoin",
                    "5426": "solana",
                    "2010": "cardano",
                    "5": "dogecoin",
                    "3890": "matic-network",
                    "6636": "polkadot",
                    "5805": "avalanche-2",
                    "2": "litecoin",
                    "7083": "uniswap",
                    "3794": "cosmos",
                    "1975": "chainlink",
                    "1321": "ethereum-classic",
                }
                cg_coin_id = id_mapping.get(coin_id)
                if not cg_coin_id:
                    print(f"[CoinService._fetch_crypto_chart_data] Не найден маппинг для ID {coin_id}, используем как есть")
                    cg_coin_id = coin_id
            except Exception as e:
                print(f"[CoinService._fetch_crypto_chart_data] Ошибка при получении CoinGecko ID: {e}")
                cg_coin_id = coin_id
        
        try:
            # Получаем исторические данные через CoinGecko market_chart endpoint
            print(f"[CoinService._fetch_crypto_chart_data] Запрашиваем данные за {days} дней для CoinGecko ID: {cg_coin_id}")
            
            chart_data_response = await self.client.get(
                f"/coins/{cg_coin_id}/market_chart",
                params={
                    "vs_currency": "usd",
                    "days": days,
                },
            )
            
            print(f"[CoinService._fetch_crypto_chart_data] Ответ от market_chart API: {str(chart_data_response)[:500]}")
            
            # Парсим данные графика
            prices = chart_data_response.get("prices", [])
            volumes = chart_data_response.get("total_volumes", [])
            
            print(f"[CoinService._fetch_crypto_chart_data] Получено {len(prices)} точек цен, {len(volumes)} точек объемов")
            
            chart_data = []
            
            # Объединяем цены и объемы
            for i, price_point in enumerate(prices):
                timestamp_ms = price_point[0]  # Unix timestamp в миллисекундах
                price = price_point[1]
                
                # Находим соответствующий объем (если есть)
                volume = 0
                if volumes and i < len(volumes):
                    volume = volumes[i][1] if len(volumes[i]) > 1 else 0
                
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
                    "price": float(price),
                    "volume": float(volume) if volume else 0,
                })
            
            # Сортируем по дате (на всякий случай)
            chart_data.sort(key=lambda x: x["date"])
            
            print(f"[CoinService._fetch_crypto_chart_data] Успешно получено {len(chart_data)} точек из CoinGecko API")
            
            return chart_data if chart_data else []
            
        except Exception as e:
            print(f"[CoinService._fetch_crypto_chart_data] Ошибка при получении исторических данных: {str(e)}")
            print(f"[CoinService._fetch_crypto_chart_data] Тип ошибки: {type(e).__name__}")
            return []
    
    
    async def get_crypto_chart(
        self,
        coin_id: str,
        period: str = "7d",  # 1d, 7d, 30d, 1y
    ) -> List[Dict]:
        """
        Получить данные графика для криптовалюты.
        Сначала пытается получить из Binance, затем fallback на CoinGecko.
        Использует кэширование для обоих источников.
        """
        # Проверяем кэш перед запросом к Binance
        cached_data = await self.cache.get_chart(coin_id, period)
        if cached_data:
            print(f"[CoinService.get_crypto_chart] ✅ Данные из кэша для {coin_id} ({period})")
            return cached_data
        
        # Используем BinanceChartAdapter для графиков
        from app.providers.binance_chart import binance_chart_adapter
        from app.core.coin_registry import coin_registry
        
        # Получаем Binance символ для монеты
        binance_symbol = coin_registry.get_external_id(coin_id, "binance")
        
        if binance_symbol:
            binance_data = await binance_chart_adapter.get_chart_data(binance_symbol, period)
            if binance_data:
                # Сохраняем в кэш
                await self.cache.set_chart(coin_id, period, binance_data)
                print(f"[CoinService.get_crypto_chart] ✅ Использованы данные из Binance для {coin_id} ({period})")
                return binance_data
        
        # Fallback на CoinGecko если монета не найдена в Binance
        # CoinGecko метод использует декоратор кэширования автоматически
        print(f"[CoinService.get_crypto_chart] Монета {coin_id} не найдена в Binance, используем CoinGecko")
        chart_data = await self._fetch_crypto_chart_data(coin_id, period)
        
        if not chart_data:
            print(f"[CoinService.get_crypto_chart] Исторические данные недоступны для {coin_id} ({period})")
        
        return chart_data


# ============================================================================
# CoinGeckoService - старый класс для обратной совместимости
# ============================================================================

class CoinGeckoService:
    """
    Старый класс для обратной совместимости.
    Делегирует все вызовы новому CoinService.
    TODO: Удалить после миграции всех мест использования на CoinService.
    """
    
    # Константы для обратной совместимости
    CACHE_TTL_TOP3000 = 3600
    CACHE_TTL_COIN_STATIC = 3600
    CACHE_TTL_COIN_PRICE = 10
    CACHE_TTL_IMAGE_URL = 604800
    CACHE_TTL_PRICE_DECIMALS = 86400
    CACHE_TTL_CHART = 60
    BATCH_PRICE_SIZE = 100
    PER_PAGE_MAX = 250
    TOP_COINS_PAGES = 12
    
    def __init__(self):
        self._service = CoinService()
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self._service.close()
    
    @staticmethod
    def get_price_decimals(price: float) -> int:
        """Определить количество знаков после запятой (делегирует CoinService)"""
        return CoinService.get_price_decimals(price)
    
    async def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        retry_on_rate_limit: bool = True
    ) -> Dict:
        """Выполнить запрос к API (делегирует CoinGeckoClient)"""
        return await self._service.client.get(endpoint, params, retry_on_rate_limit)
    
    def _load_coins_config(self) -> tuple[List[str], str]:
        """Загрузить список монет из конфиг-файла (делегирует CoinService)"""
        return self._service._load_coins_config()
    
    def _format_coin_data(self, coin_data: Dict, coin_id: str) -> Dict:
        """Форматировать данные монеты для фронтенда (делегирует CoinService)"""
        return self._service._format_coin_data(coin_data, coin_id)
    
    # Делегируем все методы новому CoinService
    async def get_batch_prices(self, coin_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Получить цены для нескольких монет (делегирует CoinService)"""
        return await self._service.get_batch_prices(coin_ids)
    
    async def get_crypto_list(
        self,
        limit: int = 100,
        page: int = 1,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """Получить список криптовалют (делегирует CoinService)"""
        return await self._service.get_crypto_list(limit, page, force_refresh)
    
    async def get_crypto_list_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """Получить только цены для списка монет (делегирует CoinService)"""
        return await self._service.get_crypto_list_prices(coin_ids)
    
    async def get_crypto_details(self, coin_id: str) -> Dict:
        """Получить детали криптовалюты (делегирует CoinService)"""
        return await self._service.get_crypto_details(coin_id)
    
    async def get_coin_image_url(self, coin_id: str) -> Optional[str]:
        """Получить URL изображения монеты (делегирует CoinService)"""
        return await self._service.get_coin_image_url(coin_id)
    
    async def get_crypto_chart(
        self,
        coin_id: str,
        period: str = "7d",
    ) -> List[Dict]:
        """Получить данные графика для криптовалюты (делегирует CoinService)"""
        return await self._service.get_crypto_chart(coin_id, period)
    
    async def refresh_top3000_cache(self) -> None:
        """Обновить кэш топ-3000 монет (устаревший метод, не используется)"""
        # TODO: Удалить после проверки, что нигде не используется
        print("[CoinGeckoService] refresh_top3000_cache устарел и не используется")
        pass


# Глобальный singleton экземпляр для переиспользования HTTP клиента
# и предотвращения утечек памяти
_coingecko_service_instance: Optional[CoinGeckoService] = None


def get_coingecko_service() -> CoinGeckoService:
    """Получить глобальный экземпляр CoinGeckoService (singleton)"""
    global _coingecko_service_instance
    if _coingecko_service_instance is None:
        _coingecko_service_instance = CoinGeckoService()
    return _coingecko_service_instance


async def close_coingecko_service():
    """Закрыть HTTP клиент глобального экземпляра CoinGeckoService"""
    global _coingecko_service_instance
    if _coingecko_service_instance is not None:
        await _coingecko_service_instance.close()
        _coingecko_service_instance = None
