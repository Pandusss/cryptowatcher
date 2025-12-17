"""
Сервис для работы с ценами монет из Redis/WebSocket
"""
import asyncio
from typing import Dict, List, Any, Optional

from app.core.redis_client import get_redis
from app.utils.cache import CoinCacheManager
from app.utils.formatters import get_price_decimals


class CoinPriceService:
    """
    Сервис для работы с ценами монет.
    Получает цены ТОЛЬКО из Redis кэша (который обновляется через Binance/OKX WebSocket).
    CoinGecko НЕ используется для цен.
    """
    
    def __init__(self):
        self.cache = CoinCacheManager()
    
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        """
        Получить текущую цену монеты.
        
        Args:
            coin_id: внутренний ID монеты
            
        Returns:
            Словарь с данными о цене или None
        """
        cached_price = await self.cache.get_price(coin_id)
        if cached_price:
            return cached_price
        
        # Если цены нет в кэше, возвращаем None (цены должны приходить из WebSocket)
        return None
    
    async def get_prices_batch(self, coin_ids: List[str]) -> Dict[str, Optional[Dict]]:
        """
        Получить цены для нескольких монет.
        
        Args:
            coin_ids: список внутренних ID монет
            
        Returns:
            Словарь {coin_id: price_data или None}
        """
        result = {}
        
        # Используем Redis pipeline для batch чтения
        redis = await get_redis()
        if not redis:
            return {coin_id: None for coin_id in coin_ids}
        
        try:
            async with redis.pipeline() as pipe:
                for coin_id in coin_ids:
                    pipe.get(self.cache._get_price_key(coin_id))
                
                results = await pipe.execute()
            
            for i, coin_id in enumerate(coin_ids):
                price_data = results[i]
                if price_data:
                    if isinstance(price_data, bytes):
                        price_data = price_data.decode('utf-8')
                    
                    try:
                        price_dict = json.loads(price_data) if price_data else None
                        result[coin_id] = price_dict
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        print(f"[CoinPriceService] Ошибка десериализации цены для {coin_id}: {e}")
                        result[coin_id] = None
                else:
                    result[coin_id] = None
        
        except Exception as e:
            print(f"[CoinPriceService] Ошибка batch чтения цен: {e}")
            result = {coin_id: None for coin_id in coin_ids}
        
        return result
    
    async def get_crypto_list_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Получить цены для списка монет ТОЛЬКО из Redis (обновляются через Binance/OKX WebSocket).
        CoinGecko НЕ используется для цен - только для статики (картинки, названия).
        
        Args:
            coin_ids: список внутренних ID монет
            
        Returns:
            Словарь {coin_id: price_data}
        """
        if not coin_ids:
            return {}
        
        print(f"[CoinPriceService] Загружаем цены для {len(coin_ids)} монет из Redis...")
        
        # Читаем цены ТОЛЬКО из Redis кэша
        prices_dict = {}
        redis = await get_redis()
        
        if redis:
            # Читаем все цены параллельно
            tasks = []
            for coin_id in coin_ids:
                tasks.append(self.cache.get_price(coin_id))
            
            cached_prices = await asyncio.gather(*tasks, return_exceptions=True)
            
            for coin_id, cached_price in zip(coin_ids, cached_prices):
                if isinstance(cached_price, Exception):
                    print(f"[CoinPriceService] Ошибка чтения цены для {coin_id}: {cached_price}")
                    continue
                    
                if cached_price and cached_price.get("price", 0) > 0:
                    prices_dict[coin_id] = {
                        "price": cached_price.get("price", 0),
                        "percent_change_24h": cached_price.get("percent_change_24h", 0),
                        "volume_24h": cached_price.get("volume_24h", 0),
                        "priceDecimals": cached_price.get("priceDecimals", get_price_decimals(cached_price.get("price", 0))),
                    }
        else:
            print("[CoinPriceService]  ⚠️ Redis недоступен, цены недоступны (CoinGecko НЕ используется для цен)")
            # НЕ используем CoinGecko как fallback - цены должны приходить только из WebSocket
        
        print(f"[CoinPriceService] Получено цен: {len(prices_dict)} из {len(coin_ids)} запрошенных")
        return prices_dict
    
    async def refresh_price(self, coin_id: str) -> bool:
        """
        Принудительно удалить цену из кэша (чтобы обновилась через WebSocket).
        
        Args:
            coin_id: внутренний ID монеты
            
        Returns:
            True если успешно, False если ошибка
        """
        redis = await get_redis()
        if not redis:
            return False
        
        try:
            price_key = self.cache._get_price_key(coin_id)
            await redis.delete(price_key)
            return True
        except Exception as e:
            print(f"[CoinPriceService] Ошибка удаления цены для {coin_id}: {e}")
            return False
    
    async def set_price(self, coin_id: str, price_data: Dict) -> bool:
        """
        Установить цену монеты в кэш.
        Используется WebSocket обработчиком для обновления цен.
        
        Args:
            coin_id: внутренний ID монеты
            price_data: словарь с данными о цене
            
        Returns:
            True если успешно, False если ошибка
        """
        return await self.cache.set_price(coin_id, price_data)
    
    async def get_prices_for_formatting(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Получить цены для форматирования в список монет.
        Упрощенный вариант метода для использования в CoinService.
        
        Args:
            coin_ids: список внутренних ID монет
            
        Returns:
            Словарь {coin_id: price_data}
            
        Note:
            Если цена не найдена, возвращает пустой словарь для этой монеты
        """
        prices = await self.get_prices_batch(coin_ids)
        result = {}
        for coin_id, price_dict in prices.items():
            if price_dict and price_dict.get("price", 0) > 0:
                result[coin_id] = {
                    "price": price_dict.get("price", 0),
                    "percent_change_24h": price_dict.get("percent_change_24h", 0),
                    "volume_24h": price_dict.get("volume_24h", 0),
                    "priceDecimals": price_dict.get("priceDecimals", get_price_decimals(price_dict.get("price", 0))),
                }
        return result

import json  # Для десериализации