"""
Сервис для работы со статическими данными монет из CoinGecko API
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional


from app.core.coin_registry import coin_registry
from app.providers.coingecko_client import CoinGeckoClient
from app.utils.cache import CoinCacheManager


class CoinStaticService:
    """
    Сервис для работы со статическими данными монет (название, символ, изображение и т.д.)
    Использует CoinGecko API для получения статики и кэширует результаты в Redis.
    """
    
    def __init__(self):
        self.client = CoinGeckoClient()
        self.cache = CoinCacheManager()
        self._logger = logging.getLogger("CoinStaticService")

    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.close()
    
    async def get_static_data(self, coin_id: str) -> Optional[Dict]:
        """
        Получить статические данные для одной монеты.
        
        Args:
            coin_id: внутренний ID монеты
            
        Returns:
            Словарь с статическими данными или None
        """
        # Сначала проверяем кэш
        cached_static = await self.cache.get_static(coin_id)
        if cached_static:
            return cached_static
        
        # Если нет в кэше, загружаем из CoinGecko
        coin = coin_registry.get_coin(coin_id)
        if not coin:
            return None
        
        coingecko_id = coin.external_ids.get("coingecko")
        if not coingecko_id:
            return None
        
        try:
            data = await self.client.get(
                f"/coins/{coingecko_id}",
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
            
            static_data = {
                "id": coin_id,
                "name": data.get("name", ""),
                "symbol": data.get("symbol", "").upper(),
                "slug": coin_id,
                "imageUrl": image_url,
            }
            
            # Сохраняем в кэш
            await self.cache.set_static(coin_id, static_data)
            
            # Сохраняем иконку отдельно
            if image_url:
                await self.cache.set_image_url(coin_id, image_url)
            
            return static_data
            
        except Exception as e:
            self._logger.error(f"Ошибка получения статики для {coin_id}: {e}")
            return None
    
    async def get_static_data_batch(self, coin_ids: List[str]) -> Dict[str, Optional[Dict]]:
        """
        Получить статические данные для нескольких монет.
        
        Args:
            coin_ids: список внутренних ID монет
            
        Returns:
            Словарь {coin_id: static_data или None}
        """
        if not coin_ids:
            return {}
        
        # Проверяем кэш для всех монет
        result = {}
        coins_to_fetch = []
        
        for coin_id in coin_ids:
            cached_static = await self.cache.get_static(coin_id)
            if cached_static:
                result[coin_id] = cached_static
            else:
                coins_to_fetch.append(coin_id)
        
        # Если все есть в кэше, возвращаем
        if not coins_to_fetch:
            return result
        
        # Загружаем оставшиеся из CoinGecko
        coingecko_ids = []
        coingecko_to_internal = {}
        
        for internal_id in coins_to_fetch:
            coin = coin_registry.get_coin(internal_id)
            if coin:
                coingecko_id = coin.external_ids.get("coingecko")
                if coingecko_id:
                    coingecko_ids.append(coingecko_id)
                    coingecko_to_internal[coingecko_id] = internal_id
                else:
                    self._logger.warning(f"Монета {internal_id} не имеет CoinGecko ID")
                    result[internal_id] = None
            else:
                self._logger.warning(f"Монета {internal_id} не найдена в реестре")
                result[internal_id] = None
        
        if not coingecko_ids:
            return result
        
        try:
            ids_param = ','.join(coingecko_ids)
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
            
            # Обрабатываем загруженные данные
            for coin_id in coins_to_fetch:
                if coin_id in coins_dict:
                    coin_data = coins_dict[coin_id]
                    static_data = {
                        "id": coin_id,
                        "name": coin_data.get("name", ""),
                        "symbol": coin_data.get("symbol", "").upper(),
                        "slug": coin_id,
                        "imageUrl": coin_data.get("image", ""),
                    }
                    
                    result[coin_id] = static_data
                    
                    # Сохраняем в кэш
                    await self.cache.set_static(coin_id, static_data)
                    
                    # Сохраняем иконку отдельно
                    image_url = coin_data.get("image", "")
                    if image_url:
                        await self.cache.set_image_url(coin_id, image_url)
                else:
                    result[coin_id] = None
                    print(f"[CoinStaticService] ⚠️ Монета {coin_id} не найдена в ответе API")
        
        except Exception as e:
            print(f"[CoinStaticService] Ошибка получения статики для batch: {e}")
            # Для монет, которые не удалось загрузить, возвращаем None
            for coin_id in coins_to_fetch:
                if coin_id not in result:
                    result[coin_id] = None
        
        return result
    
    async def refresh_static_data(self, coin_id: str) -> bool:
        """
        Принудительно обновить статические данные монеты.
        
        Args:
            coin_id: внутренний ID монеты
            
        Returns:
            True если успешно, False если ошибка
        """
        # Удаляем из кэша
        redis = await self.cache._get_redis()
        if redis:
            static_key = self.cache._get_static_key(coin_id)
            image_key = self.cache._get_image_url_key(coin_id)
            await redis.delete(static_key, image_key)
        
        # Загружаем заново
        static_data = await self.get_static_data(coin_id)
        return static_data is not None