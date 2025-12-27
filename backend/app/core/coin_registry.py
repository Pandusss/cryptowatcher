"""
CoinRegistry - centralized coin registry with mapping to all sources

Loads configuration from coins.json and provides unified interface
for working with coins and their mapping to external sources.
"""
import json
import hashlib
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger("CoinRegistry")


@dataclass
class CoinConfig:
    id: str
    name: str
    symbol: str
    enabled: bool
    external_ids: Dict[str, str]  # Mapping to external sources (coingecko, binance, etc.)
    price_priority: List[str]  # Priority of sources for prices


class CoinRegistry:
    
    _instance: Optional['CoinRegistry'] = None
    _coins: Dict[str, CoinConfig] = {}
    _coin_order: List[str] = []  # Coin order from config
    _config_path: Optional[Path] = None
    _last_modified: Optional[float] = None  # Time of last file modification
    _config_hash: Optional[str] = None  # Hash of entire config content
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._coin_order = [] 
            cls._instance._config_path = Path(__file__).parent / "configs" / "coins.json"
            cls._instance._load_config()
        return cls._instance
    
    def _check_and_reload(self):
        if not self._config_path or not self._config_path.exists():
            return
        
        try:
            current_mtime = os.path.getmtime(self._config_path)
            if self._last_modified is None or current_mtime > self._last_modified:
                self._load_config()
        except Exception as e:
            logger.warning(f"Error checking configuration changes: {e}")
    
    def _load_config(self):
        try:
            if not self._config_path:
                self._config_path = Path(__file__).parent / "configs" / "coins.json"
            
            if not self._config_path.exists():
                logger.warning(f"Config file not found: {self._config_path}")
                return
            
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
                config_data = json.loads(config_content)
            
            if not config_data or 'coins' not in config_data:
                logger.warning(f"Invalid configuration format")
                return
            
            # Calculate hash of entire config content (to detect any changes)
            normalized_content = json.dumps(config_data, sort_keys=True, ensure_ascii=False)
            new_config_hash = hashlib.md5(normalized_content.encode('utf-8')).hexdigest()
            
            coins_data = config_data['coins']
            old_coin_ids = set(self._coins.keys())
            self._coins = {}
            self._coin_order = []  # Preserve order from JSON
            
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
                self._coin_order.append(coin_config.id)
            
            # Update modification time and hash
            self._last_modified = os.path.getmtime(self._config_path)
            self._config_hash = new_config_hash
            
        except Exception as e:
            logger.error(f"Configuration loading error: {e}", exc_info=True)
    
    def get_coin(self, coin_id: str) -> Optional[CoinConfig]:
        return self._coins.get(coin_id)
    
    def get_all_coins(self, enabled_only: bool = True) -> List[CoinConfig]:
        coins = list(self._coins.values())
        if enabled_only:
            coins = [c for c in coins if c.enabled]
        return coins
    
    def get_coin_ids(self, enabled_only: bool = True) -> List[str]:
        # Check if config has changed
        self._check_and_reload()
        
        if enabled_only:
            # Filter by enabled and preserve order from config
            result = []
            for coin_id in self._coin_order:
                coin = self._coins.get(coin_id)
                if coin and coin.enabled:
                    result.append(coin_id)
            return result
        else:
            # Return all in order from config
            return self._coin_order.copy()
    
    def get_external_id(self, coin_id: str, source: str) -> Optional[str]:
        coin = self.get_coin(coin_id)
        if not coin:
            return None
        return coin.external_ids.get(source)
    
    def get_price_providers(self, coin_id: str) -> List[str]:
        coin = self.get_coin(coin_id)
        if not coin:
            return []
        return coin.price_priority.copy()
    
    def find_coin_by_external_id(self, source: str, external_id: str) -> Optional[CoinConfig]:
        for coin in self._coins.values():
            if coin.external_ids.get(source) == external_id:
                return coin
        return None
    
    def find_coin_by_symbol(self, symbol: str, enabled_only: bool = True) -> Optional[CoinConfig]:
        symbol_upper = symbol.upper()
        for coin in self._coins.values():
            if enabled_only and not coin.enabled:
                continue
            if coin.symbol.upper() == symbol_upper:
                return coin
        return None
    
    def get_coins_by_source(self, source: str) -> List[CoinConfig]:
        return [
            coin for coin in self._coins.values()
            if coin.enabled and source in coin.external_ids
        ]
    
    def reload(self):
        self._load_config()
    
    def get_config_hash(self) -> Optional[str]:
        return self._config_hash


# Global registry instance
coin_registry = CoinRegistry()