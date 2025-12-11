"""
CoinRegistry - централизованный реестр монет с маппингом на все источники

Загружает конфигурацию из coins.json и предоставляет единый интерфейс
для работы с монетами и их маппингом на внешние источники.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass


@dataclass
class CoinConfig:
    """Конфигурация одной монеты"""
    id: str
    name: str
    symbol: str
    enabled: bool
    external_ids: Dict[str, str]  # Маппинг на внешние источники (coingecko, binance, etc.)
    price_priority: List[str]  # Приоритет источников для цен


class CoinRegistry:
    """Централизованный реестр монет"""
    
    _instance: Optional['CoinRegistry'] = None
    _coins: Dict[str, CoinConfig] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Загрузить конфигурацию из coins.json"""
        try:
            # Путь к конфигу относительно core/coin_registry.py
            config_path = Path(__file__).parent / "configs" / "coins.json"
            
            if not config_path.exists():
                print(f"[CoinRegistry] ⚠️ Конфиг-файл не найден: {config_path}")
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            if not config_data or 'coins' not in config_data:
                print(f"[CoinRegistry] ⚠️ Неверный формат конфига")
                return
            
            coins_data = config_data['coins']
            self._coins = {}
            
            for coin_key, coin_data in coins_data.items():
                coin_config = CoinConfig(
                    id=coin_data.get('id', coin_key),
                    name=coin_data.get('name', ''),
                    symbol=coin_data.get('symbol', ''),
                    enabled=coin_data.get('enabled', True),
                    external_ids=coin_data.get('external_ids', {}),
                    price_priority=coin_data.get('price_priority', [])
                )
                self._coins[coin_config.id] = coin_config
            
            print(f"[CoinRegistry] ✅ Загружено {len(self._coins)} монет из конфига")
            
        except Exception as e:
            print(f"[CoinRegistry] ❌ Ошибка загрузки конфига: {e}")
    
    def get_coin(self, coin_id: str) -> Optional[CoinConfig]:
        """Получить конфигурацию монеты по ID"""
        return self._coins.get(coin_id)
    
    def get_all_coins(self, enabled_only: bool = True) -> List[CoinConfig]:
        """Получить все монеты"""
        coins = list(self._coins.values())
        if enabled_only:
            coins = [c for c in coins if c.enabled]
        return coins
    
    def get_coin_ids(self, enabled_only: bool = True) -> List[str]:
        """Получить список всех ID монет"""
        coins = self.get_all_coins(enabled_only)
        return [c.id for c in coins]
    
    def get_external_id(self, coin_id: str, source: str) -> Optional[str]:
        """
        Получить внешний ID монеты для указанного источника
        
        Args:
            coin_id: Внутренний ID монеты
            source: Источник (coingecko, binance, kucoin, etc.)
            
        Returns:
            Внешний ID или None если не найден
        """
        coin = self.get_coin(coin_id)
        if not coin:
            return None
        return coin.external_ids.get(source)
    
    def get_price_providers(self, coin_id: str) -> List[str]:
        """
        Получить список провайдеров цен для монеты в порядке приоритета
        
        Args:
            coin_id: Внутренний ID монеты
            
        Returns:
            Список провайдеров (binance, kucoin, etc.)
        """
        coin = self.get_coin(coin_id)
        if not coin:
            return []
        return coin.price_priority.copy()
    
    def find_coin_by_external_id(self, source: str, external_id: str) -> Optional[CoinConfig]:
        """
        Найти монету по внешнему ID источника
        
        Args:
            source: Источник (coingecko, binance, etc.)
            external_id: Внешний ID
            
        Returns:
            Конфигурация монеты или None
        """
        for coin in self._coins.values():
            if coin.external_ids.get(source) == external_id:
                return coin
        return None
    
    def get_coins_by_source(self, source: str) -> List[CoinConfig]:
        """
        Получить все монеты, доступные на указанном источнике
        
        Args:
            source: Источник (coingecko, binance, etc.)
            
        Returns:
            Список конфигураций монет
        """
        return [
            coin for coin in self._coins.values()
            if coin.enabled and source in coin.external_ids
        ]
    
    def reload(self):
        """Перезагрузить конфигурацию из файла"""
        self._load_config()


# Глобальный экземпляр реестра
coin_registry = CoinRegistry()

