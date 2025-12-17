"""
Главный сервис для работы с криптовалютами (публичный интерфейс)

Архитектура:
- CoinStaticService: статика из CoinGecko
- CoinPriceService: цены из Redis/WebSocket
- CoinCacheService: работа с кэшем
- CoinService: оркестрация бизнес-логики

Примечания:
- CoinGecko используется ТОЛЬКО для статических данных (id, name, symbol, imageUrl)
- Цены получаются из Binance/OKX WebSocket (binance_websocket.py, okx_websocket.py)
- Графики получаются из Binance/OKX (binance_chart.py, okx_chart.py)
"""
import hashlib
import asyncio
from typing import Dict, List, Any, Optional

from app.core.redis_client import get_redis
from app.services.coin_static_service import CoinStaticService
from app.services.coin_price_service import CoinPriceService
from app.services.coin_cache_service import CoinCacheService
from app.utils.formatters import get_price_decimals


class CoinService:
    
    def __init__(self):
        self.static_service = CoinStaticService()
        self.price_service = CoinPriceService()
        self.cache_service = CoinCacheService()
    
    async def close(self):
        await self.static_service.close()
    
    
    def _load_coins_config(self) -> tuple[List[str], str]:
        """
        Загрузить список монет из реестра и вычислить хеш конфига.
        """
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
    
    def _format_coin_data(self, static_data: Dict, price_data: Optional[Dict] = None) -> Dict:
        """
        Форматировать данные монеты для ответа API.
        """
        if price_data:
            price = price_data.get("price", 0)
            percent_change_24h = price_data.get("percent_change_24h", 0)
            volume_24h = price_data.get("volume_24h", 0)
            price_decimals = price_data.get("priceDecimals", get_price_decimals(price))
        else:
            price = 0
            percent_change_24h = 0
            volume_24h = 0
            price_decimals = 2
        
        return {
            "id": static_data.get("id", ""),
            "name": static_data.get("name", ""),
            "symbol": static_data.get("symbol", "").upper(),
            "slug": static_data.get("slug", ""),
            "imageUrl": static_data.get("imageUrl", ""),
            "quote": {
                "USD": {
                    "price": price,
                    "percent_change_24h": percent_change_24h,
                    "volume_24h": volume_24h,
                }
            },
            "priceDecimals": price_decimals,
        }
    
    async def get_crypto_list_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Получить цены для списка монет ТОЛЬКО из Redis (обновляются через Binance/OKX WebSocket).
        CoinGecko НЕ используется для цен - только для статики (картинки, названия).
        """
        return await self.price_service.get_crypto_list_prices(coin_ids)
    
    async def get_crypto_list(
        self,
        limit: int = 100,
        page: int = 1,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """
        Получить список монет со статикой и ценами.
        
        Args:
            limit: максимальное количество монет (не используется в текущей реализации)
            page: номер страницы (не используется)
            force_refresh: принудительно обновить данные
            
        Returns:
            Список отформатированных монет
        """
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
                print(f"[CoinService.get_crypto_list]  🔄 Обнаружено изменение конфига (хеш: {cached_hash[:8]}... -> {config_hash[:8]}...)")
                print(f"[CoinService.get_crypto_list] Очищаем кэш списка монет и статики...")
                # Очищаем кэш списка монет
                await redis.delete("coins_list:filtered")
                # Очищаем кэш статики для всех монет
                await self.cache_service.clear_all_static_cache()
                
                # Обновляем хеш
                await redis.set(cached_hash_key, config_hash)
            elif not cached_hash:
                # Первый запуск - сохраняем хеш
                await redis.set(cached_hash_key, config_hash)
        
        print(f"\n[CoinService.get_crypto_list] ===== НАЧАЛО ОБРАБОТКИ =====")
        print(f"[CoinService.get_crypto_list] Всего монет в конфиге: {len(config_coins)}")
        
        # Получаем данные из кэша
        cached_data = await self.cache_service.get_static_and_prices_batch(config_coins)
        
        # Анализируем кэш
        formatted_coins = []
        coins_to_fetch = []
        coins_with_full_cache = 0
        coins_with_static_only = 0
        coins_with_no_cache = 0
        
        for coin_id in config_coins:
            coin_cache = cached_data.get(coin_id, {"static": None, "price": None})
            cached_static = coin_cache.get("static")
            cached_price = coin_cache.get("price")
            
            if cached_static:
                if cached_price:
                    # Полностью в кэше
                    coin = self._format_coin_data(cached_static, cached_price)
                    formatted_coins.append(coin)
                    coins_with_full_cache += 1
                else:
                    # Только статика в кэше
                    coin = self._format_coin_data(cached_static, None)
                    formatted_coins.append(coin)
                    coins_with_static_only += 1
            else:
                # Нет в кэше
                coins_with_no_cache += 1
                coins_to_fetch.append(coin_id)
        
        print(f"[CoinService.get_crypto_list] === РЕЗУЛЬТАТЫ ПРОВЕРКИ КЭША ===")
        print(f"[CoinService.get_crypto_list] Полностью в кэше (статика + цены): {coins_with_full_cache}")
        print(f"[CoinService.get_crypto_list] Только статика в кэше: {coins_with_static_only}")
        print(f"[CoinService.get_crypto_list] Нет в кэше: {coins_with_no_cache}")
        print(f"[CoinService.get_crypto_list] ️ Цены берутся ТОЛЬКО из кэша Redis (обновляются каждые 10 сек)")
        
        # Если force_refresh, загружаем все заново
        if force_refresh:
            coins_to_fetch = config_coins.copy()
            coins_with_no_cache = len(config_coins)
            formatted_coins = []  # Отбрасываем кэшированные данные
            
        # Если все в кэше и не требуется принудительное обновление, возвращаем немедленно
        if formatted_coins and not coins_to_fetch:
            # Сортируем по порядку из конфига
            coin_order = {coin_id: idx for idx, coin_id in enumerate(config_coins)}
            formatted_coins.sort(key=lambda x: coin_order.get(x.get("id"), 9999))
            print(f"[CoinService.get_crypto_list] ✅ Все {len(formatted_coins)} монет из кэша, возвращаем немедленно")
            return formatted_coins
        
        # Загружаем статические данные для монет, которых нет в кэше
        if coins_to_fetch:
            print(f"\n[CoinService.get_crypto_list] === ЗАГРУЗКА СТАТИЧЕСКИХ ДАННЫХ ===")
            print(f"[CoinService.get_crypto_list] Монет для загрузки: {len(coins_to_fetch)}")
            
            # Используем CoinStaticService для загрузки
            static_data_dict = await self.static_service.get_static_data_batch(coins_to_fetch)
            
            # Получаем цены для загруженных монет
            price_data_dict = await self.price_service.get_prices_for_formatting(coins_to_fetch)
            
            # Формируем итоговый список
            for coin_id in coins_to_fetch:
                static_data = static_data_dict.get(coin_id)
                if not static_data:
                    print(f"[CoinService.get_crypto_list] ️ Монета {coin_id} не найдена в ответе API")
                    continue
                    
                price_data = price_data_dict.get(coin_id)
                coin = self._format_coin_data(static_data, price_data)
                formatted_coins.append(coin)
        
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
        Получить детальную информацию о монете.
        """
        # Получаем статику
        static_data = await self.static_service.get_static_data(coin_id)
        if not static_data:
            # Если статики нет, пытаемся получить через cache
            static_data = await self.cache_service.get_static(coin_id)
            if not static_data:
                return {
                    "id": coin_id,
                    "name": "",
                    "symbol": "",
                    "currentPrice": 0,
                    "priceChange24h": 0,
                    "priceChangePercent24h": 0,
                    "imageUrl": "",
                    "priceDecimals": 2,
                }
        
        # Получаем цену
        price_data = await self.price_service.get_price(coin_id)
        
        if price_data:
            print(f"[CoinService.get_crypto_details] ✅ Цена {coin_id} из кэша Redis: ${price_data.get('price', 0)}")
        else:
            print(f"[CoinService.get_crypto_details] ️ Цена {coin_id} недоступна (обновится через 10 секунд)")
        
        price = price_data.get("price", 0) if price_data else 0
        price_change_24h = price_data.get("volume_24h", 0) if price_data else 0
        price_change_percent_24h = price_data.get("percent_change_24h", 0) if price_data else 0
        price_decimals = price_data.get("priceDecimals", get_price_decimals(price)) if price_data else get_price_decimals(price)
        
        coin = {
            "id": static_data.get("id", coin_id),
            "name": static_data.get("name", ""),
            "symbol": static_data.get("symbol", "").upper(),
            "currentPrice": price,
            "priceChange24h": price_change_24h,
            "priceChangePercent24h": price_change_percent_24h,
            "imageUrl": static_data.get("imageUrl", ""),
            "priceDecimals": price_decimals,
        }
        
        return coin
    
    async def refresh_coin_data(self, coin_id: str) -> bool:
        """
        Принудительно обновить данные монеты.
        """
        try:
            # Очищаем кэш статики
            await self.cache_service.clear_static_cache(coin_id)
            
            # Очищаем кэш цены
            await self.cache_service.clear_price_cache(coin_id)
            
            # Загружаем заново
            static_data = await self.static_service.get_static_data(coin_id)
            return static_data is not None
        except Exception as e:
            print(f"[CoinService] Ошибка обновления данных для {coin_id}: {e}")
            return False
