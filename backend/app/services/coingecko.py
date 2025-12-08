import httpx
from typing import List, Dict, Any
from datetime import datetime, timedelta
from app.core.config import settings
from app.core.redis_client import get_redis


class CoinGeckoService:
    BASE_URL = "https://api.coingecko.com/api/v3"
    
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
    
    async def get_crypto_list(
        self,
        limit: int = 100,
        page: int = 1,
    ) -> List[Dict]:
        """Получить список криптовалют"""
        # Проверяем кэш в Redis (если доступен)
        redis = await get_redis()
        if redis:
            try:
                cache_key = f"coins_list:{limit}:{page}"
                cached = await redis.get(cache_key)
                
                if cached:
                    import json
                    print(f"[get_crypto_list] Данные из кэша Redis")
                    return json.loads(cached)
            except Exception:
                pass  # Продолжаем без кэша
        
        # CoinGecko использует per_page и page для пагинации
        per_page = min(limit, 250)  # Максимум 250 на страницу
        
        data = await self._make_request(
            "/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": page,
                "sparkline": False,
            },
        )
        
        print(f"\n[get_crypto_list] Получено монет: {len(data)}")
        if data:
            print(f"[get_crypto_list] Первая монета (сырые данные): {str(data[0])[:300]}")
        
        # Форматируем данные для фронтенда (совместимость с текущим форматом)
        formatted_coins = []
        for coin_data in data:
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
            
            formatted_coins.append({
                "id": coin_data.get("id", ""),  # CoinGecko использует id как строку (например, "bitcoin")
                "name": coin_data.get("name", ""),
                "symbol": coin_data.get("symbol", "").upper(),
                "slug": coin_data.get("id", ""),  # Используем id как slug
                "imageUrl": image_url,  # URL изображения из CoinGecko
                "quote": {
                    "USD": {
                        "price": price,
                        "percent_change_24h": coin_data.get("price_change_percentage_24h"),
                        "volume_24h": coin_data.get("total_volume"),
                    }
                },
            })
        
        # Кэшируем на 15 минут (если Redis доступен)
        if redis:
            try:
                cache_key = f"coins_list:{limit}:{page}"
                import json
                await redis.setex(cache_key, 900, json.dumps(formatted_coins))  # 15 минут = 900 секунд
            except Exception:
                pass  # Пропускаем кэширование если ошибка
        
        print(f"[get_crypto_list] Отформатировано монет: {len(formatted_coins)}")
        if formatted_coins:
            print(f"[get_crypto_list] Первая монета (отформатированные данные): {formatted_coins[0]}")
        
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
                    print(f"[get_crypto_details] Данные из кэша Redis")
                    return json.loads(cached)
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
        
        # Объединяем данные
        coin = {
            "id": data.get("id", coin_id),
            "name": data.get("name", ""),
            "symbol": data.get("symbol", "").upper(),
            "currentPrice": float(current_price) if current_price else 0,
            "priceChange24h": float(price_change_24h) if price_change_24h else 0,
            "priceChangePercent24h": float(price_change_percent_24h) if price_change_percent_24h else 0,
            "imageUrl": image_url,
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
            chart_data = []  # Возвращаем пустой список, фронтенд использует mock данные
        
        # Кэшируем результат на 1 минуту (если Redis доступен)
        if redis and chart_data:
            try:
                cache_key = f"coin_chart:{coin_id}:{period}"
                import json
                await redis.setex(cache_key, 60, json.dumps(chart_data))  # Кэш на 1 минуту
            except Exception:
                pass
        
        if not chart_data:
            print(f"[get_crypto_chart] Исторические данные недоступны. Фронтенд будет использовать mock данные.")
        
        return chart_data

