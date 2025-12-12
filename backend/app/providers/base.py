"""
Базовые классы для адаптеров провайдеров данных
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseStaticAdapter(ABC):
    
    @abstractmethod
    async def get_coin_static_data(self, coin_id: str) -> Optional[Dict]:
        """
        Получить статические данные монеты
        
        Args:
            coin_id: Внешний ID монеты для этого провайдера
            
        Returns:
            Словарь с данными: {id, name, symbol, imageUrl} или None
        """
        pass
    
    @abstractmethod
    async def get_coins_static_data(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Получить статические данные для нескольких монет
        
        Args:
            coin_ids: Список внешних ID монет
            
        Returns:
            Словарь {coin_id: {id, name, symbol, imageUrl}}
        """
        pass
    
    @abstractmethod
    async def get_coin_image_url(self, coin_id: str) -> Optional[str]:
        """
        Получить URL изображения монеты
        
        Args:
            coin_id: Внешний ID монеты
            
        Returns:
            URL изображения или None
        """
        pass


class BasePriceAdapter(ABC):
    """Базовый класс для адаптеров цен"""
    
    @abstractmethod
    async def get_price(self, coin_id: str) -> Optional[Dict]:
        """
        Получить текущую цену монеты
        
        Args:
            coin_id: Внешний ID монеты для этого провайдера
            
        Returns:
            Словарь с данными: {price, percent_change_24h, volume_24h} или None
        """
        pass
    
    @abstractmethod
    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """
        Получить цены для нескольких монет
        
        Args:
            coin_ids: Список внешних ID монет
            
        Returns:
            Словарь {coin_id: {price, percent_change_24h, volume_24h}}
        """
        pass
    
    @abstractmethod
    def is_available(self, coin_id: str) -> bool:
        pass
    
    async def _get_price_from_redis(
        self,
        coin_id: str,
        source: str,
        adapter_name: str
    ) -> Optional[Dict]:
        """
        Общий метод для чтения цены из Redis кэша
        
        Args:
            coin_id: Внешний ID монеты (например, "BTCUSDT" для Binance)
            source: Источник данных ("binance", "okx")
            adapter_name: Имя адаптера для логирования (например, "BinancePriceAdapter")
            
        Returns:
            Словарь с данными цены или None
        """
        from app.core.coin_registry import coin_registry
        from app.core.redis_client import get_redis
        import json
        
        # Находим внутренний ID монеты по внешнему символу
        internal_coin = coin_registry.find_coin_by_external_id(source, coin_id)
        if not internal_coin:
            return None
        
        # Получаем Redis клиент
        redis = await get_redis()
        if not redis:
            return None
        
        try:
            # Формируем ключ кэша
            cache_key = f"coin_price:{internal_coin.id}"
            cached_data = await redis.get(cache_key)
            
            if cached_data:
                # Десериализуем JSON (обрабатываем bytes и str)
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode('utf-8')
                price_data = json.loads(cached_data)
                return price_data
                
        except Exception as e:
            print(f"[{adapter_name}] Ошибка чтения цены для {coin_id}: {e}")
        
        return None


class BaseChartAdapter(ABC):
    
    @abstractmethod
    async def get_chart_data(
        self,
        coin_id: str,
        period: str = "7d"
    ) -> Optional[List[Dict]]:
        """
        Получить данные графика
        
        Args:
            coin_id: Внешний ID монеты
            period: Период (1d, 7d, 30d, 1y)
            
        Returns:
            Список точек графика [{"date": str, "price": float, "volume": float}] или None
        """
        pass
    
    @abstractmethod
    def is_available(self, coin_id: str) -> bool:
        """
        Проверить, доступна ли монета на этом провайдере
        
        Args:
            coin_id: Внешний ID монеты
            
        Returns:
            True если доступна, False иначе
        """
        pass

