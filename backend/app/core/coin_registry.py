"""
CoinRegistry - централизованный реестр монет с маппингом на все источники

Загружает конфигурацию из coins.json и предоставляет единый интерфейс
для работы с монетами и их маппингом на внешние источники.
"""
import json
import hashlib
import os
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
    _coin_order: List[str] = []  # Порядок монет из конфига
    _config_path: Optional[Path] = None
    _last_modified: Optional[float] = None  # Время последней модификации файла
    _config_hash: Optional[str] = None  # Хеш всего содержимого конфига
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._coin_order = []  # Инициализируем порядок
            cls._instance._config_path = Path(__file__).parent / "configs" / "coins.json"
            cls._instance._load_config()
        return cls._instance
    
    def _check_and_reload(self):
        """Проверить, изменился ли файл конфига, и перезагрузить при необходимости"""
        if not self._config_path or not self._config_path.exists():
            return
        
        try:
            current_mtime = os.path.getmtime(self._config_path)
            if self._last_modified is None or current_mtime > self._last_modified:
                print(f"[CoinRegistry] 🔄 Обнаружены изменения в конфиге, перезагружаем...")
                self._load_config()
        except Exception as e:
            print(f"[CoinRegistry] ⚠️ Ошибка при проверке изменений конфига: {e}")
    
    def _load_config(self):
        """Загрузить конфигурацию из coins.json"""
        try:
            if not self._config_path:
                self._config_path = Path(__file__).parent / "configs" / "coins.json"
            
            if not self._config_path.exists():
                print(f"[CoinRegistry] ⚠️ Конфиг-файл не найден: {self._config_path}")
                return
            
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
                config_data = json.loads(config_content)
            
            if not config_data or 'coins' not in config_data:
                print(f"[CoinRegistry] ⚠️ Неверный формат конфига")
                return
            
            # Вычисляем хеш всего содержимого конфига (для обнаружения любых изменений)
            # Сортируем ключи для стабильности хеша
            normalized_content = json.dumps(config_data, sort_keys=True, ensure_ascii=False)
            new_config_hash = hashlib.md5(normalized_content.encode('utf-8')).hexdigest()
            
            coins_data = config_data['coins']
            old_coin_ids = set(self._coins.keys())
            self._coins = {}
            self._coin_order = []  # Сохраняем порядок из JSON
            
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
                self._coin_order.append(coin_config.id)  # Сохраняем порядок
            
            # Обновляем время модификации и хеш
            self._last_modified = os.path.getmtime(self._config_path)
            old_config_hash = self._config_hash
            self._config_hash = new_config_hash
            
            new_coin_ids = set(self._coins.keys())
            removed_coins = old_coin_ids - new_coin_ids
            added_coins = new_coin_ids - old_coin_ids
            config_changed = old_config_hash != new_config_hash
            
            if removed_coins or added_coins:
                print(f"[CoinRegistry] ✅ Перезагружено {len(self._coins)} монет из конфига")
                if removed_coins:
                    print(f"[CoinRegistry]   - Удалено монет: {len(removed_coins)} ({', '.join(list(removed_coins)[:5])}{'...' if len(removed_coins) > 5 else ''})")
                if added_coins:
                    print(f"[CoinRegistry]   - Добавлено монет: {len(added_coins)} ({', '.join(list(added_coins)[:5])}{'...' if len(added_coins) > 5 else ''})")
            elif config_changed:
                print(f"[CoinRegistry] ✅ Перезагружено {len(self._coins)} монет из конфига (обнаружены изменения в данных монет)")
                print(f"[CoinRegistry]   - Хеш конфига изменился: {old_config_hash[:8] if old_config_hash else 'N/A'}... -> {new_config_hash[:8]}...")
            else:
                print(f"[CoinRegistry] ✅ Загружено {len(self._coins)} монет из конфига")
            
        except Exception as e:
            print(f"[CoinRegistry] ❌ Ошибка загрузки конфига: {e}")
            import traceback
            traceback.print_exc()
    
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
        """
        Получить список всех ID монет в порядке из конфига
        
        Args:
            enabled_only: Только включенные монеты
            
        Returns:
            Список ID монет в порядке из конфига
        """
        # Проверяем, изменился ли конфиг
        self._check_and_reload()
        
        if enabled_only:
            # Фильтруем по enabled и сохраняем порядок из конфига
            result = []
            for coin_id in self._coin_order:
                coin = self._coins.get(coin_id)
                if coin and coin.enabled:
                    result.append(coin_id)
            return result
        else:
            # Возвращаем все в порядке из конфига
            return self._coin_order.copy()
    
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
    
    def get_config_hash(self) -> Optional[str]:
        """Получить хеш текущего конфига"""
        return self._config_hash


# Глобальный экземпляр реестра
coin_registry = CoinRegistry()

