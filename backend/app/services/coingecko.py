import httpx
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.core.config import settings
from app.core.redis_client import get_redis


class CoinGeckoService:
    """Сервис для работы с CoinGecko API"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # Константы для кэширования
    CACHE_TTL_TOP3000 = 3600  # 1 час в секундах
    CACHE_TTL_COIN_STATIC = 3600  # 1 час в секундах (статические данные: id, name, symbol, imageUrl)
    CACHE_TTL_COIN_PRICE = 10  # 10 секунд (цены везде: список монет и детали монеты)
    CACHE_TTL_IMAGE_URL = 604800  # 7 дней в секундах
    CACHE_TTL_PRICE_DECIMALS = 86400  # 1 день в секундах
    CACHE_TTL_CHART = 60  # 1 минута в секундах
    
    # Константы для пагинации
    BATCH_PRICE_SIZE = 100  # Максимум монет в одном batch запросе цен
    
    @staticmethod
    def get_price_decimals(price: float) -> int:
        """Определяет количество знаков после запятой на основе цены"""
        if price >= 1:
            return 2
        if price >= 0.1:
            return 3
        if price >= 0.01:
            return 4
        if price >= 0.001:
            return 5
        if price >= 0.0001:
            return 6
        if price >= 0.00001:
            return 7
        if price >= 0.000001:
            return 8
        if price >= 0.0000001:
            return 9
        return 10
    
    def __init__(self):
        # CoinGecko не требует API ключа для базового использования
        # Но можно использовать API ключ для увеличения лимитов
        self.headers = {
            "Accept": "application/json",
        }
        # Если есть API ключ в настройках, используем его
        self.api_key = getattr(settings, 'COINGECKO_API_KEY', '') or ''
        if self.api_key:
            # CoinGecko использует заголовок x-cg-demo-api-key для Demo API ключей
            # или x-cg-pro-api-key для Pro API ключей
            # Попробуем оба варианта, начиная с demo
            self.headers["x-cg-demo-api-key"] = self.api_key
            print(f"[CoinGeckoService] Используется API ключ (первые 10 символов): {self.api_key[:10]}...")
        else:
            print("[CoinGeckoService] API ключ не установлен, используются базовые лимиты")
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None, retry_on_rate_limit: bool = True) -> Dict:
        """Выполнить запрос к CoinGecko API"""
        async with httpx.AsyncClient() as client:
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    url = f"{self.BASE_URL}{endpoint}"
                    request_params = params or {}
                    print(f"\n[CoinGecko API] Request: {url}")
                    print(f"[CoinGecko API] Params: {request_params}")
                    if self.api_key:
                        print(f"[CoinGecko API] Используется API ключ")
                    
                    response = await client.get(
                        url,
                        headers=self.headers,
                        params=request_params,
                        timeout=30.0,  # CoinGecko может быть медленнее
                    )
                    
                    # Обработка rate limit (429)
                    if response.status_code == 429:
                        if retry_on_rate_limit and retry_count < max_retries - 1:
                            # Получаем время ожидания из заголовка Retry-After или используем экспоненциальную задержку
                            retry_after = response.headers.get("Retry-After")
                            wait_time = int(retry_after) if retry_after and retry_after.isdigit() else (2 ** retry_count) * 2
                            
                            print(f"[CoinGecko API] Rate limit достигнут. Ожидание {wait_time} секунд перед повтором...")
                            import asyncio
                            await asyncio.sleep(wait_time)
                            retry_count += 1
                            continue
                        else:
                            error_detail = f"HTTP {response.status_code}: {response.text}"
                            print(f"[CoinGecko API] ERROR: {error_detail}")
                            print(f"[CoinGecko API] Совет: Установите COINGECKO_API_KEY в .env для увеличения лимитов")
                            response.raise_for_status()
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    print(f"[CoinGecko API] Response status: {response.status_code}")
                    print(f"[CoinGecko API] Response data (first 500 chars): {str(data)[:500]}")
                    
                    return data
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and retry_on_rate_limit and retry_count < max_retries - 1:
                        retry_after = e.response.headers.get("Retry-After")
                        wait_time = int(retry_after) if retry_after and retry_after.isdigit() else (2 ** retry_count) * 2
                        
                        print(f"[CoinGecko API] Rate limit достигнут. Ожидание {wait_time} секунд перед повтором...")
                        import asyncio
                        await asyncio.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        error_detail = f"HTTP {e.response.status_code}: {e.response.text}"
                        print(f"[CoinGecko API] ERROR: {error_detail}")
                        if e.response.status_code == 429:
                            print(f"[CoinGecko API] Совет: Установите COINGECKO_API_KEY в .env для увеличения лимитов")
                        raise
                except Exception as e:
                    print(f"[CoinGecko API] Request failed: {str(e)}")
                    raise
            
            # Если дошли сюда, значит все попытки исчерпаны
            raise Exception("Превышено максимальное количество попыток из-за rate limit")
    
    def _load_coins_config(self) -> tuple[List[str], str]:
        """Загрузить список ID монет из конфиг-файла и его хеш для проверки изменений"""
        try:
            # Путь к конфиг-файлу относительно текущего файла
            config_path = Path(__file__).parent.parent / "config" / "coins.json"
            if not config_path.exists():
                print(f"[get_crypto_list] Конфиг-файл не найден: {config_path}")
                return [], ""
            
            with open(config_path, 'r', encoding='utf-8') as f:
                coins_list = json.load(f)
            
            # Вычисляем хеш содержимого файла для проверки изменений
            import hashlib
            with open(config_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            print(f"[get_crypto_list] Загружено {len(coins_list)} монет из конфиг-файла (хеш: {file_hash[:8]}...)")
            return coins_list, file_hash
        except Exception as e:
            print(f"[get_crypto_list] Ошибка загрузки конфиг-файла: {e}")
            return [], ""
    
    def _format_coin_data(self, coin_data: Dict, coin_id: str) -> Dict:
        """Форматировать данные монеты для фронтенда"""
        price = coin_data.get("current_price", 0)
        
        # Убеждаемся, что цена не None и является числом
        if price is None:
            price = 0
        elif not isinstance(price, (int, float)):
            try:
                price = float(price)
            except (ValueError, TypeError):
                price = 0
        
        # Получаем URL изображения из CoinGecko
        image_url = coin_data.get("image", "")
        
        # Вычисляем количество знаков после запятой
        price_decimals = self.get_price_decimals(price)
        
        return {
            "id": coin_id,
            "name": coin_data.get("name", ""),
            "symbol": coin_data.get("symbol", "").upper(),
            "slug": coin_id,
            "imageUrl": image_url,
            "priceDecimals": price_decimals,
            "quote": {
                "USD": {
                    "price": price,
                    "percent_change_24h": coin_data.get("price_change_percentage_24h"),
                    "volume_24h": coin_data.get("total_volume"),
                }
            },
        }
    
    async def refresh_top3000_cache(self) -> None:
        """Обновить кэш топ-3000 монет в фоновом режиме"""
        print(f"[refresh_top3000_cache] Начинаем обновление кэша топ-3000 монет...")
        try:
            redis = await get_redis()
            if not redis:
                print("[refresh_top3000_cache] Redis недоступен, пропускаем обновление")
                return
            
            per_page = self.PER_PAGE_MAX
            total_pages = self.TOP_COINS_PAGES
            all_coins_list = []
            all_coins_dict = {}
            
            for page_num in range(1, total_pages + 1):
                try:
                    data = await self._make_request(
                        "/coins/markets",
                        params={
                            "vs_currency": "usd",
                            "order": "market_cap_desc",
                            "per_page": per_page,
                            "page": page_num,
                            "sparkline": False,
                        },
                    )
                    
                    # Добавляем монеты в словарь и список
                    for coin_data in data:
                        coin_id = coin_data.get("id", "")
                        if coin_id:
                            all_coins_dict[coin_id] = coin_data
                            all_coins_list.append(coin_data)
                    
                    print(f"[refresh_top3000_cache] Получено {len(data)} монет со страницы {page_num}")
                    
                    # Если получили меньше монет, чем ожидалось, значит достигли конца списка
                    if len(data) < per_page:
                        break
                        
                except Exception as e:
                    print(f"[refresh_top3000_cache] Ошибка при получении страницы {page_num}: {e}")
                    break
            
            # Кэшируем топ-3000 на 1 час
            if all_coins_list:
                try:
                    top3000_cache_key = "coins_list:top3000"
                    await redis.setex(top3000_cache_key, self.CACHE_TTL_TOP3000, json.dumps(all_coins_list))
                    print(f"[refresh_top3000_cache] Топ-3000 монет успешно обновлены в кэше: {len(all_coins_list)} монет")
                except Exception as e:
                    print(f"[refresh_top3000_cache] Ошибка при сохранении топ-3000 в кэш: {e}")
            else:
                print("[refresh_top3000_cache] Не удалось получить данные для кэширования")
                
        except Exception as e:
            print(f"[refresh_top3000_cache] Ошибка при обновлении кэша топ-3000: {e}")
    
    async def get_batch_prices(self, coin_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Получить цены для нескольких монет за один запрос через batch API
        Использует /simple/price endpoint CoinGecko
        
        Args:
            coin_ids: Список ID монет (например, ['bitcoin', 'ethereum'])
            
        Returns:
            Словарь вида {'bitcoin': {'usd': 50000.0, 'usd_24h_change': 2.5, 'usd_24h_vol': 1000000}, ...}
        """
        if not coin_ids:
            print("[get_batch_prices] Список монет пуст")
            return {}
        
        print(f"[get_batch_prices] Запрашиваем цены для {len(coin_ids)} монет через batch API...")
        
        try:
            all_prices = {}
            total_batches = (len(coin_ids) + self.BATCH_PRICE_SIZE - 1) // self.BATCH_PRICE_SIZE
            
            if total_batches == 1:
                print(f"[get_batch_prices] ✅ ОДИН запрос для всех {len(coin_ids)} монет (лимит: {self.BATCH_PRICE_SIZE})")
            else:
                print(f"[get_batch_prices] Разбиваем на {total_batches} батчей (лимит: {self.BATCH_PRICE_SIZE} монет на батч)")
            
            # Разбиваем на батчи, если монет больше BATCH_PRICE_SIZE
            for i in range(0, len(coin_ids), self.BATCH_PRICE_SIZE):
                batch = coin_ids[i:i + self.BATCH_PRICE_SIZE]
                batch_num = i // self.BATCH_PRICE_SIZE + 1
                ids_param = ','.join(batch)
                
                print(f"[get_batch_prices] Батч {batch_num}/{total_batches}: отправляем запрос для {len(batch)} монет...")
                print(f"[get_batch_prices] URL параметр ids: {ids_param[:100]}{'...' if len(ids_param) > 100 else ''}")
                
                try:
                    data = await self._make_request(
                        "/simple/price",
                        params={
                            "ids": ids_param,
                            "vs_currencies": "usd",
                            "include_24hr_change": "true",
                            "include_24hr_vol": "true",
                        },
                    )
                    
                    # Обрабатываем ответ
                    batch_count = 0
                    for coin_id, price_data in data.items():
                        if price_data and 'usd' in price_data:
                            all_prices[coin_id] = {
                                'usd': price_data.get('usd', 0),
                                'usd_24h_change': price_data.get('usd_24h_change', 0),
                                'usd_24h_vol': price_data.get('usd_24h_vol', 0),
                            }
                            batch_count += 1
                    
                    print(f"[get_batch_prices] Батч {batch_num}/{total_batches}: получено {batch_count} цен")
                    
                except Exception as e:
                    print(f"[get_batch_prices] Ошибка при получении батча {batch_num}: {e}")
                    continue
            
            print(f"[get_batch_prices] Всего получено цен: {len(all_prices)} из {len(coin_ids)} запрошенных")
            return all_prices
            
        except Exception as e:
            print(f"[get_batch_prices] Критическая ошибка при получении batch цен: {e}")
            return {}
    
    async def get_crypto_list(
        self,
        limit: int = 100,
        page: int = 1,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """Получить список криптовалют, отфильтрованный по конфиг-файлу"""
        # Загружаем список монет из конфиг-файла и его хеш
        config_coins, config_hash = self._load_coins_config()
        
        # Если конфиг пустой, возвращаем пустой список
        if not config_coins:
            print("[get_crypto_list] Конфиг-файл пустой, возвращаем пустой список")
            return []
        
        redis = await get_redis()
        
        # Проверяем кэш для каждой монеты индивидуально
        formatted_coins = []
        coins_to_fetch = []  # Монеты, которых нет в кэше
        
        print(f"\n[get_crypto_list] ===== НАЧАЛО ОБРАБОТКИ =====")
        print(f"[get_crypto_list] Всего монет в конфиге: {len(config_coins)}")
        print(f"[get_crypto_list] Проверяем кэш для каждой монеты...")
        
        coins_with_full_cache = 0
        coins_with_static_only = 0
        coins_with_no_cache = 0
        
        for coin_id in config_coins:
            cached_coin = None
            
            # Проверяем кэш статических данных и цен отдельно
            if redis and not force_refresh:
                try:
                    # Проверяем статические данные (1 час)
                    static_cache_key = f"coin_static:{coin_id}"
                    cached_static = await redis.get(static_cache_key)
                    
                    # Проверяем цены (5 минут)
                    price_cache_key = f"coin_price:{coin_id}"
                    cached_price = await redis.get(price_cache_key)
                    
                    if cached_static:
                        cached_coin = json.loads(cached_static)
                        
                        # Если есть кэш цен, обновляем цены в объекте
                        if cached_price:
                            price_data = json.loads(cached_price)
                            cached_coin["quote"] = {
                                "USD": {
                                    "price": price_data.get("price", 0),
                                    "percent_change_24h": price_data.get("percent_change_24h"),
                                    "volume_24h": price_data.get("volume_24h"),
                                }
                            }
                            cached_coin["priceDecimals"] = price_data.get("priceDecimals", self.get_price_decimals(price_data.get("price", 0)))
                            coins_with_full_cache += 1
                        else:
                            # Если цен нет, но статические данные есть - нужно обновить только цены
                            coins_with_static_only += 1
                            coins_to_fetch.append(coin_id)
                            continue
                        
                        # Проверяем и добавляем priceDecimals, если его нет
                        if "priceDecimals" not in cached_coin:
                            price = cached_coin.get("quote", {}).get("USD", {}).get("price", 0)
                            cached_coin["priceDecimals"] = self.get_price_decimals(price)
                except Exception as e:
                    print(f"[get_crypto_list] Ошибка при чтении кэша для {coin_id}: {e}")
            
            if cached_coin:
                formatted_coins.append(cached_coin)
            else:
                # Монета не найдена в кэше, нужно запросить из API
                coins_with_no_cache += 1
                coins_to_fetch.append(coin_id)
        
        print(f"[get_crypto_list] === РЕЗУЛЬТАТЫ ПРОВЕРКИ КЭША ===")
        print(f"[get_crypto_list] Полностью в кэше (статика + цены): {coins_with_full_cache}")
        print(f"[get_crypto_list] Только статика в кэше (цены обновятся через 10 сек): {coins_with_static_only}")
        print(f"[get_crypto_list] Нет в кэше (нужны все данные): {coins_with_no_cache}")
        print(f"[get_crypto_list] Всего нужно загрузить: {len(coins_to_fetch)}")
        
        # ВАЖНО: НЕ делаем запросы к API для цен - они обновляются каждые 10 секунд в фоновом режиме
        # Если цены нет в кэше, просто возвращаем монету с ценой 0 (обновится через 10 секунд)
        print(f"[get_crypto_list] ⚠️ Цены берутся ТОЛЬКО из кэша Redis (обновляются каждые 10 сек в фоне)")
        
        # Для монет без цен в кэше, добавляем их с ценой 0 (обновится через 10 секунд)
        for coin_id in config_coins:
            existing_coin = next((c for c in formatted_coins if c.get("id") == coin_id), None)
            if not existing_coin:
                # Монета не найдена - нужно загрузить статику из API
                coins_to_fetch.append(coin_id)
            elif existing_coin.get("quote", {}).get("USD", {}).get("price", 0) == 0:
                # Монета есть, но цены нет в кэше - это нормально, обновится через 10 секунд
                pass
        
        # Если есть монеты, которых нет в кэше (нужны статические данные), запрашиваем их из API
        if coins_to_fetch:
            print(f"\n[get_crypto_list] === ЗАГРУЗКА СТАТИЧЕСКИХ ДАННЫХ ===")
            print(f"[get_crypto_list] Монет для загрузки: {len(coins_to_fetch)}")
            print(f"[get_crypto_list] Список монет: {', '.join(coins_to_fetch[:10])}{'...' if len(coins_to_fetch) > 10 else ''}")
            
            try:
                # CoinGecko позволяет передать ids через запятую в /coins/markets
                ids_param = ','.join(coins_to_fetch)
                print(f"[get_crypto_list] Отправляем запрос к /coins/markets с ids параметром...")
                coins_data = await self._make_request(
                    "/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "ids": ids_param,
                        "order": "market_cap_desc",
                        "per_page": len(coins_to_fetch),
                        "sparkline": False,
                    },
                )
                
                # Преобразуем в словарь для быстрого поиска
                coins_dict = {coin_data.get("id"): coin_data for coin_data in coins_data if coin_data.get("id")}
                print(f"[get_crypto_list] Получено статических данных: {len(coins_dict)} из {len(coins_to_fetch)} запрошенных")
                
            except Exception as e:
                print(f"[get_crypto_list] Ошибка при получении статических данных через batch: {e}")
                coins_dict = {}
            
            # Обрабатываем монеты, которые нужно было загрузить
            saved_static_count = 0
            for coin_id in coins_to_fetch:
                if coin_id in coins_dict:
                    coin_data = coins_dict[coin_id]
                    formatted_coin = self._format_coin_data(coin_data, coin_id)
                    
                    # Проверяем, есть ли цена в кэше Redis (обновляется каждые 10 секунд)
                    cached_price = None
                    if redis:
                        try:
                            price_cache_key = f"coin_price:{coin_id}"
                            cached_price_data = await redis.get(price_cache_key)
                            if cached_price_data:
                                cached_price = json.loads(cached_price_data)
                        except Exception:
                            pass
                    
                    # Используем цену из кэша, если есть, иначе 0 (обновится через 10 секунд)
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
                        # Цены нет в кэше - обновится через 10 секунд в фоновом режиме
                        formatted_coin["quote"] = {
                            "USD": {
                                "price": 0,
                                "percent_change_24h": 0,
                                "volume_24h": 0,
                            }
                        }
                        formatted_coin["priceDecimals"] = 2
                    
                    formatted_coins.append(formatted_coin)
                    
                    # Сохраняем ТОЛЬКО статические данные в кэш (цены обновляются каждые 10 сек в фоне)
                    if redis:
                        try:
                            static_data = {
                                "id": formatted_coin.get("id"),
                                "name": formatted_coin.get("name"),
                                "symbol": formatted_coin.get("symbol"),
                                "slug": formatted_coin.get("slug"),
                                "imageUrl": formatted_coin.get("imageUrl"),
                            }
                            static_cache_key = f"coin_static:{coin_id}"
                            await redis.setex(static_cache_key, self.CACHE_TTL_COIN_STATIC, json.dumps(static_data))
                            saved_static_count += 1
                        except Exception as e:
                            print(f"[get_crypto_list] Ошибка при сохранении статики для {coin_id}: {e}")
                else:
                    print(f"[get_crypto_list] ⚠️ Монета {coin_id} не найдена в ответе API")
            
            print(f"[get_crypto_list] Сохранено статических данных в кэш: {saved_static_count}")
            print(f"[get_crypto_list] ⚠️ Цены НЕ сохраняются из API - берутся ТОЛЬКО из кэша Redis (обновляются каждые 10 сек)")
        
        # Сортируем монеты по порядку из конфига
        coin_order = {coin_id: idx for idx, coin_id in enumerate(config_coins)}
        formatted_coins.sort(key=lambda x: coin_order.get(x.get("id"), 9999))
        
        print(f"\n[get_crypto_list] === ИТОГОВЫЕ РЕЗУЛЬТАТЫ ===")
        print(f"[get_crypto_list] Итого отформатировано монет: {len(formatted_coins)}")
        print(f"[get_crypto_list] Ожидалось монет из конфига: {len(config_coins)}")
        if formatted_coins:
            first_coin_price = formatted_coins[0].get('quote', {}).get('USD', {}).get('price', 0)
            print(f"[get_crypto_list] Первая монета: {formatted_coins[0].get('name')} (${first_coin_price})")
        print(f"[get_crypto_list] ===== КОНЕЦ ОБРАБОТКИ =====\n")
        
        return formatted_coins
    
    async def get_crypto_list_static_only(
        self,
        limit: int = 100,
        page: int = 1,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """Получить данные монет из кэша (статика + цены) - для быстрой загрузки"""
        config_coins, config_hash = self._load_coins_config()
        
        if not config_coins:
            return []
        
        redis = await get_redis()
        formatted_coins = []
        coins_to_fetch = []
        
        print(f"\n[get_crypto_list_static_only] Загружаем данные из кэша для {len(config_coins)} монет...")
        
        # Проверяем кэш статических данных И цен
        for coin_id in config_coins:
            cached_static = None
            cached_price = None
            
            if redis and not force_refresh:
                try:
                    # Проверяем статические данные
                    static_cache_key = f"coin_static:{coin_id}"
                    cached_static_data = await redis.get(static_cache_key)
                    if cached_static_data:
                        cached_static = json.loads(cached_static_data)
                    
                    # Проверяем цены
                    price_cache_key = f"coin_price:{coin_id}"
                    cached_price_data = await redis.get(price_cache_key)
                    if cached_price_data:
                        cached_price = json.loads(cached_price_data)
                except Exception as e:
                    print(f"[get_crypto_list_static_only] Ошибка чтения кэша для {coin_id}: {e}")
            
            if cached_static:
                # Формируем монету из кэша
                coin_data = {
                    "id": cached_static.get("id", coin_id),
                    "name": cached_static.get("name", ""),
                    "symbol": cached_static.get("symbol", ""),
                    "imageUrl": cached_static.get("imageUrl", ""),
                    "quote": {
                        "USD": {
                            "price": cached_price.get("price", 0) if cached_price else 0,
                            "percent_change_24h": cached_price.get("percent_change_24h", 0) if cached_price else 0,
                            "volume_24h": cached_price.get("volume_24h", 0) if cached_price else 0,
                        }
                    },
                    "priceDecimals": cached_price.get("priceDecimals") if cached_price else self.get_price_decimals(cached_price.get("price", 0) if cached_price else 0),
                }
                formatted_coins.append(coin_data)
            else:
                # Если статики нет в кэше, нужно загрузить из API
                coins_to_fetch.append(coin_id)
        
        print(f"[get_crypto_list_static_only] Из кэша: {len(formatted_coins)} монет (статика + цены), нужно загрузить: {len(coins_to_fetch)}")
        
        # Если все данные в кэше, возвращаем немедленно
        if formatted_coins and not coins_to_fetch:
            coin_order = {coin_id: idx for idx, coin_id in enumerate(config_coins)}
            formatted_coins.sort(key=lambda x: coin_order.get(x.get("id"), 9999))
            print(f"[get_crypto_list_static_only] ✅ Все {len(formatted_coins)} монет из кэша (статика + цены), возвращаем немедленно")
            return formatted_coins
        
        # Если есть недостающие данные (статика), загружаем их из API
        # Но цены все равно берем из кэша (если есть), так как они обновляются каждые 10 секунд
        if coins_to_fetch:
            try:
                ids_param = ','.join(coins_to_fetch)
                coins_data = await self._make_request(
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
                
                # Добавляем недостающие монеты в правильном порядке
                for coin_id in config_coins:
                    if coin_id in coins_to_fetch and coin_id in coins_dict:
                        coin_data = coins_dict[coin_id]
                        image_url = coin_data.get("image", "")
                        
                        # Проверяем, есть ли цена в кэше
                        cached_price = None
                        if redis:
                            try:
                                price_cache_key = f"coin_price:{coin_id}"
                                cached_price_data = await redis.get(price_cache_key)
                                if cached_price_data:
                                    cached_price = json.loads(cached_price_data)
                            except Exception:
                                pass
                        
                        static_coin = {
                            "id": coin_id,
                            "name": coin_data.get("name", ""),
                            "symbol": coin_data.get("symbol", "").upper(),
                            "imageUrl": image_url,
                            "quote": {
                                "USD": {
                                    "price": cached_price.get("price", 0) if cached_price else 0,
                                    "percent_change_24h": cached_price.get("percent_change_24h", 0) if cached_price else 0,
                                    "volume_24h": cached_price.get("volume_24h", 0) if cached_price else 0,
                                }
                            },
                            "priceDecimals": cached_price.get("priceDecimals") if cached_price else self.get_price_decimals(cached_price.get("price", 0) if cached_price else 0),
                        }
                        # Вставляем в правильную позицию
                        coin_index = config_coins.index(coin_id)
                        formatted_coins.insert(coin_index, static_coin)
                        
                        # Сохраняем статику в кэш
                        if redis:
                            try:
                                static_data = {
                                    "id": coin_id,
                                    "name": static_coin["name"],
                                    "symbol": static_coin["symbol"],
                                    "imageUrl": image_url,
                                }
                                static_cache_key = f"coin_static:{coin_id}"
                                await redis.setex(static_cache_key, self.CACHE_TTL_COIN_STATIC, json.dumps(static_data))
                            except Exception:
                                pass
            except Exception as e:
                print(f"[get_crypto_list_static_only] Ошибка при загрузке статических данных: {e}")
        
        # Убеждаемся, что порядок соответствует конфигу
        coin_order = {coin_id: idx for idx, coin_id in enumerate(config_coins)}
        formatted_coins.sort(key=lambda x: coin_order.get(x.get("id"), 9999))
        
        print(f"[get_crypto_list_static_only] ✅ Возвращаем {len(formatted_coins)} монет из кэша (статика + цены)")
        return formatted_coins
    
    async def get_crypto_list_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """Получить только цены для списка монет - для обновления после загрузки статики"""
        if not coin_ids:
            return {}
        
        print(f"\n[get_crypto_list_prices] Загружаем цены для {len(coin_ids)} монет...")
        
        # Получаем цены через batch API
        batch_prices = await self.get_batch_prices(coin_ids)
        
        # Форматируем результат
        prices_dict = {}
        redis = await get_redis()
        
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
                if redis:
                    try:
                        price_cache_key = f"coin_price:{coin_id}"
                        await redis.setex(price_cache_key, self.CACHE_TTL_COIN_PRICE, json.dumps(price_data))
                    except Exception:
                        pass
        
        print(f"[get_crypto_list_prices] Получено цен: {len(prices_dict)} из {len(coin_ids)} запрошенных")
        return prices_dict
    
    async def get_crypto_details(self, coin_id: str) -> Dict:
        """Получить детали криптовалюты - ВСЕГДА использует цены из кэша Redis"""
        redis = await get_redis()
        
        # Сначала получаем статические данные (из кэша или API)
        cached_static = None
        if redis:
            try:
                static_cache_key = f"coin_static:{coin_id}"
                cached_static_data = await redis.get(static_cache_key)
                if cached_static_data:
                    cached_static = json.loads(cached_static_data)
            except Exception:
                pass
        
        # Получаем цену ИЗ КЭША Redis (обновляется каждые 10 секунд)
        cached_price = None
        if redis:
            try:
                price_cache_key = f"coin_price:{coin_id}"
                cached_price_data = await redis.get(price_cache_key)
                if cached_price_data:
                    cached_price = json.loads(cached_price_data)
                    print(f"[get_crypto_details] ✅ Цена {coin_id} из кэша Redis: ${cached_price.get('price', 0)}")
            except Exception as e:
                print(f"[get_crypto_details] Ошибка чтения цены из кэша: {e}")
        
        # Если есть статика и цена в кэше - возвращаем сразу
        if cached_static and cached_price:
            coin = {
                "id": cached_static.get("id", coin_id),
                "name": cached_static.get("name", ""),
                "symbol": cached_static.get("symbol", "").upper(),
                "currentPrice": cached_price.get("price", 0),
                "priceChange24h": cached_price.get("volume_24h", 0),  # Используем volume_24h как временное значение
                "priceChangePercent24h": cached_price.get("percent_change_24h", 0),
                "imageUrl": cached_static.get("imageUrl", ""),
                "priceDecimals": cached_price.get("priceDecimals", self.get_price_decimals(cached_price.get("price", 0))),
            }
            print(f"[get_crypto_details] ✅ Все данные из кэша Redis")
            return coin
        
        # Если статики нет в кэше, загружаем из API
        if not cached_static:
            data = await self._make_request(
                f"/coins/{coin_id}",
                params={
                    "localization": False,
                    "tickers": False,
                    "market_data": False,  # Не нужны данные рынка, цена из кэша
                    "community_data": False,
                    "developer_data": False,
                    "sparkline": False,
                },
            )
            
            image_url = data.get("image", {}).get("large") or data.get("image", {}).get("small")
            
            # Сохраняем статику в кэш
            if redis:
                try:
                    static_data = {
                        "id": data.get("id", coin_id),
                        "name": data.get("name", ""),
                        "symbol": data.get("symbol", "").upper(),
                        "imageUrl": image_url,
                    }
                    static_cache_key = f"coin_static:{coin_id}"
                    await redis.setex(static_cache_key, self.CACHE_TTL_COIN_STATIC, json.dumps(static_data))
                    
                    # Сохраняем иконку отдельно
                    if image_url:
                        image_cache_key = f"coin_image_url:{coin_id}"
                        await redis.setex(image_cache_key, self.CACHE_TTL_IMAGE_URL, image_url)
                except Exception as e:
                    print(f"[get_crypto_details] Ошибка сохранения статики в кэш: {e}")
            
            cached_static = {
                "id": data.get("id", coin_id),
                "name": data.get("name", ""),
                "symbol": data.get("symbol", "").upper(),
                "imageUrl": image_url,
            }
        
        # Используем цену из кэша (если есть), иначе 0 (обновится через 10 секунд)
        price = cached_price.get("price", 0) if cached_price else 0
        price_change_24h = cached_price.get("percent_change_24h", 0) if cached_price else 0
        price_decimals = cached_price.get("priceDecimals", self.get_price_decimals(price)) if cached_price else self.get_price_decimals(price)
        
        coin = {
            "id": cached_static.get("id", coin_id),
            "name": cached_static.get("name", ""),
            "symbol": cached_static.get("symbol", "").upper(),
            "currentPrice": price,
            "priceChange24h": 0,  # Не используем, так как берем из кэша
            "priceChangePercent24h": price_change_24h,
            "imageUrl": cached_static.get("imageUrl", ""),
            "priceDecimals": price_decimals,
        }
        
        print(f"[get_crypto_details] ✅ Данные монеты: цена ${price} из кэша Redis")
        return coin
    
    async def get_coin_image_url(self, coin_id: str) -> Optional[str]:
        """
        Получить URL изображения монеты из CoinGecko.
        Иконки монет не меняются, поэтому кэшируем на 7 дней.
        
        Args:
            coin_id: CoinGecko ID монеты (например, "bitcoin")
        
        Returns:
            URL изображения монеты или None если не удалось получить
        """
        redis = await get_redis()
        
        # Проверяем кэш в Redis (TTL 7 дней = 604800 секунд)
        if redis:
            try:
                cache_key = f"coin_image_url:{coin_id}"
                cached_url = await redis.get(cache_key)
                
                if cached_url:
                    print(f"[get_coin_image_url] Иконка {coin_id} из кэша Redis")
                    return cached_url
            except Exception as e:
                print(f"[get_coin_image_url] Ошибка чтения из Redis: {e}")
        
        # Если в кэше нет, запрашиваем из API
        try:
            # Используем легковесный эндпоинт для получения только базовой информации
            data = await self._make_request(
                f"/coins/{coin_id}",
                params={
                    "localization": False,
                    "tickers": False,
                    "market_data": False,  # Не нужны данные рынка
                    "community_data": False,
                    "developer_data": False,
                    "sparkline": False,
                },
            )
            
            # Извлекаем imageUrl
            image_url = data.get("image", {}).get("large") or data.get("image", {}).get("small")
            
            if image_url:
                # Сохраняем в кэш на 7 дней (604800 секунд)
                if redis:
                    try:
                        cache_key = f"coin_image_url:{coin_id}"
                        await redis.setex(cache_key, self.CACHE_TTL_IMAGE_URL, image_url)
                        print(f"[get_coin_image_url] Иконка {coin_id} сохранена в кэш на 7 дней")
                    except Exception as e:
                        print(f"[get_coin_image_url] Ошибка записи в Redis: {e}")
                
                return image_url
            else:
                print(f"[get_coin_image_url] Не найдена иконка для {coin_id}")
                return None
                
        except Exception as e:
            print(f"[get_coin_image_url] Ошибка при получении иконки для {coin_id}: {e}")
            return None
    
    async def get_crypto_chart(
        self,
        coin_id: str,
        period: str = "7d",  # 1d, 7d, 30d, 1y
    ) -> List[Dict]:
        """Получить данные графика для криптовалюты"""
        print(f"\n[get_crypto_chart] Запрос графика для coin_id={coin_id}, period={period}")
        
        # Пытаемся получить данные из кэша Redis (если доступен)
        redis = await get_redis()
        if redis:
            try:
                cache_key = f"coin_chart:{coin_id}:{period}"
                cached = await redis.get(cache_key)
                
                if cached:
                    import json
                    cached_data = json.loads(cached)
                    print(f"[get_crypto_chart] Данные из кэша Redis: {len(cached_data)} точек")
                    return cached_data
            except Exception as e:
                print(f"[get_crypto_chart] Ошибка при чтении из Redis кэша: {e}")
        
        # Преобразуем период в дни для CoinGecko API
        days_map = {
            "1d": 1,
            "7d": 7,
            "30d": 30,
            "1y": 365,
        }
        days = days_map.get(period, 7)
        
        # Если coin_id - это число (старый CoinMarketCap ID), нужно получить CoinGecko ID
        # Сначала пробуем использовать coin_id как есть (если это уже CoinGecko ID)
        cg_coin_id = coin_id
        
        # Если coin_id - число, пытаемся получить CoinGecko ID из деталей монеты
        if coin_id.isdigit():
            print(f"[get_crypto_chart] Обнаружен числовой ID, пытаемся получить CoinGecko ID")
            try:
                # Пытаемся получить детали монеты, чтобы узнать CoinGecko ID
                # Но для этого нужен символ или имя, что у нас нет
                # Вместо этого используем маппинг популярных монет
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
                    print(f"[get_crypto_chart] Не найден маппинг для ID {coin_id}, используем как есть")
                    cg_coin_id = coin_id
            except Exception as e:
                print(f"[get_crypto_chart] Ошибка при получении CoinGecko ID: {e}")
                cg_coin_id = coin_id
        
        try:
            # Получаем исторические данные через CoinGecko market_chart endpoint
            print(f"[get_crypto_chart] Запрашиваем данные за {days} дней для CoinGecko ID: {cg_coin_id}")
            
            # Формируем параметры запроса
            params = {
                "vs_currency": "usd",
                "days": days,
            }
            
            # CoinGecko автоматически определяет интервал:
            # - Для 1 дня: автоматически использует hourly (но требует Enterprise план для явного указания)
            # - Для 2-90 дней: автоматически использует hourly
            # - Для >90 дней: автоматически использует daily
            # НЕ указываем interval для бесплатного плана
            if days >= 2 and days <= 90:
                # CoinGecko автоматически использует hourly для 2-90 дней
                pass
            # Для 1 дня и >90 дней CoinGecko автоматически использует соответствующий интервал
            
            chart_data_response = await self._make_request(
                f"/coins/{cg_coin_id}/market_chart",
                params=params,
            )
            
            print(f"[get_crypto_chart] Ответ от market_chart API: {str(chart_data_response)[:500]}")
            
            # Парсим данные графика
            prices = chart_data_response.get("prices", [])
            volumes = chart_data_response.get("total_volumes", [])
            
            print(f"[get_crypto_chart] Получено {len(prices)} точек цен, {len(volumes)} точек объемов")
            
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
            
            print(f"[get_crypto_chart] Успешно получено {len(chart_data)} точек из CoinGecko API")
            
        except Exception as e:
            print(f"[get_crypto_chart] Ошибка при получении исторических данных: {str(e)}")
            print(f"[get_crypto_chart] Тип ошибки: {type(e).__name__}")
            chart_data = []
        
        # Кэшируем результат на 1 минуту (если Redis доступен)
        if redis and chart_data:
            try:
                cache_key = f"coin_chart:{coin_id}:{period}"
                import json
                await redis.setex(cache_key, self.CACHE_TTL_CHART, json.dumps(chart_data))
            except Exception:
                pass
        
        if not chart_data:
            print(f"[get_crypto_chart] Исторические данные недоступны.")
        
        return chart_data

