"""
Base class for WebSocket workers

Contains common logic for all WebSocket providers:
- Connection and reconnection management
- Error handling
- Statistics and logging
- Lifecycle management
"""
import asyncio
import json
import logging
import websockets
from abc import ABC, abstractmethod
from typing import Dict, Optional, Set, Tuple, Callable
from pathlib import Path

from app.core.redis_client import get_redis
from app.core.coin_registry import coin_registry
from app.utils.websocket_price_handler import process_price_update


class BaseWebSocketWorker(ABC):
    """
    Base class for exchange WebSocket workers
    
    Subclasses must implement:
    - _get_websocket_url() - URL for connection
    - _subscribe(ws) - subscription logic for tickers
    - _parse_message(message) - parse message and extract tickers
    - _get_symbol_extractor() - function to extract symbol from ticker
    - _get_price_extractor() - function to extract price from ticker
    - _get_price_change_extractor() - function to extract price change from ticker
    - _get_volume_extractor() - function to extract volume from ticker
    """
    
    RECONNECT_DELAY = 5  # Секунд до переподключения
    PRICE_UPDATE_INTERVAL = 0.1  # Обновляем кэш каждые 100ms
    LOG_INTERVAL = 5.0  # Интервал логирования статистики
    
    def __init__(self, source: str):
        """
        Args:
            source: Source name ("binance", "okx", etc.)
        """
        self._source = source
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._tracked_coins: Set[str] = set()  # Set of internal IDs from config
        self._last_update_time: Dict[str, float] = {}  # For tracking update frequency
        self._coins_with_updates: Set[str] = set()  # Coins with updates in the last period
        self._last_log_time: float = 0.0  # Time of last log
        self._logger = logging.getLogger(f"websocket.{source}")

    
    @abstractmethod
    def _get_websocket_url(self) -> str:
        """Get URL for WebSocket connection"""
        pass
    
    @abstractmethod
    async def _subscribe(self, ws: websockets.WebSocketClientProtocol):
        """
        Subscribe to tickers after connection
        
        Args:
            ws: WebSocket connection
        """
        pass
    
    @abstractmethod
    def _parse_message(self, message: str) -> Optional[list]:
        """
        Parse message and extract list of tickers
        
        Args:
            message: Raw message from WebSocket
            
        Returns:
            List of tickers (dict) or None if not tickers
        """
        pass
    
    @abstractmethod
    def _get_symbol_extractor(self) -> Callable[[Dict], Optional[str]]:
        """Get function to extract symbol from ticker"""
        pass
    
    @abstractmethod
    def _get_price_extractor(self) -> Callable[[Dict], float]:
        """Get function to extract price from ticker"""
        pass
    
    @abstractmethod
    def _get_price_change_extractor(self) -> Callable[[Dict], float]:
        """Get function to extract price change from ticker"""
        pass
    
    @abstractmethod
    def _get_volume_extractor(self) -> Callable[[Dict], float]:
        """Get function to extract volume from ticker"""
        pass
    
    def _load_coins_config(self) -> list[str]:
        """Load coin list from registry for this source"""
        try:
            coins = coin_registry.get_coins_by_source(self._source)
            coin_ids = [coin.id for coin in coins]
            
            print(f"[{self._get_log_prefix()}] Загружено {len(coin_ids)} монет с {self._source} из реестра")
            return coin_ids
        except Exception as e:
            print(f"[{self._get_log_prefix()}] Ошибка загрузки монет из реестра: {e}")
            return []
    
    def _get_log_prefix(self) -> str:
        """Get log prefix"""
        return f"{self._source.upper()}WebSocket"
    
    async def start(self):
        """Start WebSocket worker"""
        if self._running:
            print(f"[{self._get_log_prefix()}] Уже запущен")
            return
        
        self._running = True
        
        # Загружаем список монет из конфига
        config_coins = self._load_coins_config()
        self._tracked_coins = set(config_coins)
        
        if not self._tracked_coins:
            print(f"[{self._get_log_prefix()}] ⚠️ Нет монет для отслеживания, WebSocket не запущен")
            self._running = False
            return
        
        # Определяем, какие монеты есть в источнике
        coins_in_source = []
        coins_not_in_source = []
        for coin_id in self._tracked_coins:
            coin = coin_registry.get_coin(coin_id)
            if coin and self._source in coin.external_ids:
                coins_in_source.append(coin_id)
            else:
                coins_not_in_source.append(coin_id)
        
        print(f"[{self._get_log_prefix()}] 🚀 Запуск WebSocket worker для {len(self._tracked_coins)} монет...")
        print(f"[{self._get_log_prefix()}] 📈 Отслеживаем {len(self._tracked_coins)} монет | В {self._source}: {len(coins_in_source)} | Не в {self._source}: {len(coins_not_in_source)}")
        
        # Запускаем WebSocket loop в фоне
        self._task = asyncio.create_task(self._websocket_loop())
    
    async def stop(self):
        """Stop WebSocket worker"""
        self._running = False
        
        if self._ws:
            await self._ws.close()
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        print(f"[{self._get_log_prefix()}] ⏹️ WebSocket worker остановлен")
    
    async def close(self):
        """Close WebSocket worker (alias for stop)"""
        await self.stop()
    
    async def _websocket_loop(self):
        """Main WebSocket loop with reconnection"""
        ws_url = self._get_websocket_url()
        
        while self._running:
            try:
                print(f"[{self._get_log_prefix()}] 🔌 Подключение к {ws_url}...")
                
                async with websockets.connect(ws_url) as ws:
                    self._ws = ws
                    print(f"[{self._get_log_prefix()}] ✅ Подключено к WebSocket")
                    
                    # Подписываемся на тикеры
                    await self._subscribe(ws)
                    
                    # Обрабатываем сообщения
                    async for message in ws:
                        if not self._running:
                            break
                        
                        await self._process_message(message)
                
            except websockets.exceptions.ConnectionClosed:
                if self._running:
                    print(f"[{self._get_log_prefix()}] ⚠️ Соединение закрыто, переподключение через {self.RECONNECT_DELAY} сек...")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    break
            
            except Exception as e:
                if self._running:
                    print(f"[{self._get_log_prefix()}] ❌ Ошибка WebSocket: {e}")
                    print(f"[{self._get_log_prefix()}] Переподключение через {self.RECONNECT_DELAY} сек...")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    break
        
        print(f"[{self._get_log_prefix()}] WebSocket loop завершен")
    
    async def _process_message(self, message: str):
        """
        Process message from WebSocket
        
        Args:
            message: Raw message
        """
        try:
            # Парсим сообщение и извлекаем тикеры
            tickers = self._parse_message(message)
            
            if not tickers:
                return
            
            redis = await get_redis()
            if not redis:
                return
            
            # Статистика
            updated_count = 0
            skipped_not_in_map = 0
            skipped_not_tracked = 0
            skipped_zero_price = 0
            skipped_wrong_priority = 0
            current_time = asyncio.get_event_loop().time()
            total_tickers = len(tickers)
            
            # Получаем функции-экстракторы
            symbol_extractor = self._get_symbol_extractor()
            price_extractor = self._get_price_extractor()
            price_change_extractor = self._get_price_change_extractor()
            volume_extractor = self._get_volume_extractor()
            
            # Обрабатываем каждый тикер
            for ticker in tickers:
                if not isinstance(ticker, dict):
                    continue
                
                status, coin_id = await process_price_update(
                    ticker=ticker,
                    source=self._source,
                    symbol_extractor=symbol_extractor,
                    price_extractor=price_extractor,
                    price_change_extractor=price_change_extractor,
                    volume_extractor=volume_extractor,
                    adapter_name=self._get_log_prefix(),
                    tracked_coins=self._tracked_coins,
                    last_update_time=self._last_update_time,
                    coins_with_updates=self._coins_with_updates,
                    redis=redis,
                )
                
                if status == "updated":
                    updated_count += 1
                elif status == "skipped_not_in_map":
                    skipped_not_in_map += 1
                elif status == "skipped_not_tracked":
                    skipped_not_tracked += 1
                elif status == "skipped_wrong_priority":
                    skipped_wrong_priority += 1
                elif status == "skipped_zero_price":
                    skipped_zero_price += 1
            
            # Логируем статистику периодически
            should_log = (current_time - self._last_log_time >= self.LOG_INTERVAL)
            
            if should_log:
                self._last_log_time = current_time
                
                # Очищаем старые записи из _coins_with_updates (старше LOG_INTERVAL секунд)
                coins_to_remove = [
                    coin_id for coin_id, update_time in self._last_update_time.items()
                    if current_time - update_time > self.LOG_INTERVAL
                ]
                for coin_id in coins_to_remove:
                    self._coins_with_updates.discard(coin_id)
                
                # Детальная статистика для диагностики
                coins_with_source = len([c for c in self._tracked_coins 
                                        if coin_registry.get_coin(c) and self._source in coin_registry.get_coin(c).external_ids])
                coins_not_in_source = len(self._tracked_coins) - coins_with_source
                
                self._logger.info(f"Обновлено цен: {updated_count} монет из {total_tickers} тикеров в этом сообщении")
                self._logger.info(f"Статистика сообщения: пропущено (нет в маппинге: {skipped_not_in_map}, не отслеживаем: {skipped_not_tracked}, не приоритет {self._source}: {skipped_wrong_priority}, цена=0: {skipped_zero_price})")
                self._logger.info(f"Всего отслеживаем: {len(self._tracked_coins)} монет | В {self._source}: {coins_with_source} | Не в {self._source}: {coins_not_in_source}")
                self._logger.info(f"Уникальных монет с обновлениями за последние {self.LOG_INTERVAL} сек: {len(self._coins_with_updates)}")
                
        except Exception as e:
            print(f"[{self._get_log_prefix()}] Ошибка обработки сообщения: {e}")

