import httpx
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.config import settings
from app.core.redis_client import get_redis


class CoinGeckoService:
    BASE_URL = "https://api.coingecko.com/api/v3"
    
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
        
        print(f"[get_crypto_list] Проверяем кэш для {len(config_coins)} монет из конфига...")
        
        for coin_id in config_coins:
            cached_coin = None
            
            # Проверяем индивидуальный кэш для монеты (если не требуется принудительное обновление)
            if redis and not force_refresh:
                try:
                    cache_key = f"coin_data:{coin_id}"
                    cached = await redis.get(cache_key)
                    if cached:
                        cached_coin = json.loads(cached)
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
                coins_to_fetch.append(coin_id)
        
        print(f"[get_crypto_list] Найдено в кэше: {len(formatted_coins)}, нужно загрузить: {len(coins_to_fetch)}")
        
        # Если есть монеты, которых нет в кэше, запрашиваем их из API
        if coins_to_fetch:
            # Проверяем кэш топ-3000 монет
            all_coins_dict = {}
            top3000_cache_key = "coins_list:top3000"
            
            if redis and not force_refresh:
                try:
                    cached_top3000 = await redis.get(top3000_cache_key)
                    if cached_top3000:
                        cached_data = json.loads(cached_top3000)
                        # Преобразуем список в словарь для быстрого поиска
                        for coin_data in cached_data:
                            coin_id = coin_data.get("id", "")
                            if coin_id:
                                all_coins_dict[coin_id] = coin_data
                        print(f"[get_crypto_list] Топ-3000 монет загружены из кэша: {len(all_coins_dict)} монет")
                except Exception as e:
                    print(f"[get_crypto_list] Ошибка при чтении кэша топ-3000: {e}")
            
            # Если кэша нет или требуется обновление, запрашиваем топ-3000 из API
            if not all_coins_dict:
                per_page = 250  # Максимум 250 на страницу
                total_pages = 12  # 12 страниц * 250 = 3000 монет
                
                print(f"[get_crypto_list] Получаем топ-3000 монет из CoinGecko API...")
                all_coins_list = []  # Список для кэширования
                
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
                        
                        print(f"[get_crypto_list] Получено {len(data)} монет со страницы {page_num}")
                        
                        # Если получили меньше монет, чем ожидалось, значит достигли конца списка
                        if len(data) < per_page:
                            break
                            
                    except Exception as e:
                        print(f"[get_crypto_list] Ошибка при получении страницы {page_num}: {e}")
                        break
                
                print(f"[get_crypto_list] Всего получено {len(all_coins_dict)} уникальных монет из API")
                
                # Кэшируем топ-3000 на 1 час (3600 секунд)
                if redis and all_coins_list:
                    try:
                        await redis.setex(top3000_cache_key, 3600, json.dumps(all_coins_list))
                        print(f"[get_crypto_list] Топ-3000 монет сохранены в кэш на 1 час")
                    except Exception as e:
                        print(f"[get_crypto_list] Ошибка при сохранении топ-3000 в кэш: {e}")
            
            # Обрабатываем монеты, которые нужно было загрузить
            for coin_id in coins_to_fetch:
                if coin_id in all_coins_dict:
                    coin_data = all_coins_dict[coin_id]
                    formatted_coin = self._format_coin_data(coin_data, coin_id)
                    formatted_coins.append(formatted_coin)
                    
                    # Кэшируем монету на 1 час (3600 секунд)
                    if redis:
                        try:
                            cache_key = f"coin_data:{coin_id}"
                            await redis.setex(cache_key, 3600, json.dumps(formatted_coin))
                            
                            # Сохраняем иконку в долгосрочный кэш (7 дней)
                            image_url = formatted_coin.get("imageUrl", "")
                            if image_url:
                                image_cache_key = f"coin_image_url:{coin_id}"
                                existing = await redis.get(image_cache_key)
                                if not existing:
                                    await redis.setex(image_cache_key, 604800, image_url)
                            
                            # Сохраняем price_decimals в кэш на 1 день
                            price_decimals = formatted_coin.get("priceDecimals")
                            if price_decimals is not None:
                                decimals_cache_key = f"coin_price_decimals:{coin_id}"
                                await redis.setex(decimals_cache_key, 86400, str(price_decimals))
                        except Exception as e:
                            print(f"[get_crypto_list] Ошибка при сохранении {coin_id} в кэш: {e}")
                else:
                    print(f"[get_crypto_list] Монета {coin_id} из конфига не найдена в топ-1000")
        
        # Сортируем монеты по порядку из конфига
        coin_order = {coin_id: idx for idx, coin_id in enumerate(config_coins)}
        formatted_coins.sort(key=lambda x: coin_order.get(x.get("id"), 9999))
        
        print(f"[get_crypto_list] Итого отформатировано {len(formatted_coins)} монет")
        if formatted_coins:
            print(f"[get_crypto_list] Первая монета: {formatted_coins[0].get('name')}")
        
        return formatted_coins
    
    async def get_crypto_details(self, coin_id: str) -> Dict:
        """Получить детали криптовалюты"""
        # Проверяем кэш в Redis (если доступен)
        redis = await get_redis()
        if redis:
            try:
                cache_key = f"coin_details:{coin_id}"
                cached = await redis.get(cache_key)
                
                if cached:
                    import json
                    cached_data = json.loads(cached)
                    # Проверяем и добавляем priceDecimals, если его нет
                    if "priceDecimals" not in cached_data:
                        price = cached_data.get("currentPrice", 0)
                        cached_data["priceDecimals"] = self.get_price_decimals(price)
                    print(f"[get_crypto_details] Данные из кэша Redis")
                    return cached_data
            except Exception:
                pass  # Продолжаем без кэша
        
        # Получаем информацию о монете
        data = await self._make_request(
            f"/coins/{coin_id}",
            params={
                "localization": False,
                "tickers": False,
                "market_data": True,
                "community_data": False,
                "developer_data": False,
                "sparkline": False,
            },
        )
        
        print(f"\n[get_crypto_details] Coin data keys: {list(data.keys())}")
        
        market_data = data.get("market_data", {})
        current_price = market_data.get("current_price", {}).get("usd", 0)
        price_change_24h = market_data.get("price_change_24h", 0)
        price_change_percent_24h = market_data.get("price_change_percentage_24h", 0)
        image_url = data.get("image", {}).get("large") or data.get("image", {}).get("small")
        
        print(f"[get_crypto_details] Price: {current_price}, Change 24h: {price_change_percent_24h}%")
        
        # Вычисляем количество знаков после запятой
        current_price_float = float(current_price) if current_price else 0
        price_decimals = self.get_price_decimals(current_price_float)
        
        # Сохраняем иконку в долгосрочный кэш (7 дней) для использования в других местах
        if redis and image_url:
            try:
                cache_key = f"coin_image_url:{coin_id}"
                # Проверяем, есть ли уже в кэше (чтобы не перезаписывать)
                existing = await redis.get(cache_key)
                if not existing:
                    await redis.setex(cache_key, 604800, image_url)  # 7 дней
                    print(f"[get_crypto_details] Иконка {coin_id} сохранена в долгосрочный кэш")
            except Exception as e:
                print(f"[get_crypto_details] Ошибка сохранения иконки {coin_id} в кэш: {e}")
        
        # Сохраняем количество знаков после запятой в кэш на 1 день
        if redis:
            try:
                cache_key = f"coin_price_decimals:{coin_id}"
                await redis.setex(cache_key, 86400, str(price_decimals))  # 1 день = 86400 секунд
            except Exception as e:
                print(f"[get_crypto_details] Ошибка сохранения price_decimals {coin_id} в кэш: {e}")
        
        # Объединяем данные
        coin = {
            "id": data.get("id", coin_id),
            "name": data.get("name", ""),
            "symbol": data.get("symbol", "").upper(),
            "currentPrice": current_price_float,
            "priceChange24h": float(price_change_24h) if price_change_24h else 0,
            "priceChangePercent24h": float(price_change_percent_24h) if price_change_percent_24h else 0,
            "imageUrl": image_url,
            "priceDecimals": price_decimals,  # Количество знаков после запятой
        }
        
        print(f"\n[get_crypto_details] Final coin data: {coin}")
        
        # Кэшируем на 30 секунд (если Redis доступен)
        if redis:
            try:
                cache_key = f"coin_details:{coin_id}"
                import json
                await redis.setex(cache_key, 30, json.dumps(coin))  # 30 секунд
            except Exception:
                pass  # Пропускаем кэширование если ошибка
        
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
                        await redis.setex(cache_key, 604800, image_url)  # 7 дней
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
                await redis.setex(cache_key, 60, json.dumps(chart_data))  # Кэш на 1 минуту
            except Exception:
                pass
        
        if not chart_data:
            print(f"[get_crypto_chart] Исторические данные недоступны.")
        
        return chart_data

