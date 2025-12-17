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
    
    RECONNECT_DELAY = 5  # Seconds before reconnection
    PRICE_UPDATE_INTERVAL = 0.1  # Update cache every 100ms
    LOG_INTERVAL = 5.0  # Logging statistics interval
    
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
            
            self._logger.info(f"Loaded {len(coin_ids)} coins from {self._source} from registry")
            return coin_ids
        except Exception as e:
            self._logger.error(f"Error loading coins from registry: {e}")
            return []
    
    def _get_log_prefix(self) -> str:
        """Get log prefix"""
        return f"{self._source.upper()}WebSocket"
    
    async def start(self):
        """Start WebSocket worker"""
        if self._running:
            self._logger.warning("Already running")
            return
        
        self._running = True
        
        # Load coin list from config
        config_coins = self._load_coins_config()
        self._tracked_coins = set(config_coins)
        
        if not self._tracked_coins:
            self._logger.warning("No coins to track, WebSocket not started")
            self._running = False
            return
        
        # Determine which coins are in the source
        coins_in_source = []
        coins_not_in_source = []
        for coin_id in self._tracked_coins:
            coin = coin_registry.get_coin(coin_id)
            if coin and self._source in coin.external_ids:
                coins_in_source.append(coin_id)
            else:
                coins_not_in_source.append(coin_id)
        
        self._logger.info(f"Starting WebSocket worker for {len(self._tracked_coins)} coins")
        self._logger.info(f"Tracking {len(self._tracked_coins)} coins | In {self._source}: {len(coins_in_source)} | Not in {self._source}: {len(coins_not_in_source)}")
        
        # Start WebSocket loop in background
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
        
        self._logger.info("WebSocket worker stopped")
    
    async def close(self):
        """Close WebSocket worker (alias for stop)"""
        await self.stop()
    
    async def _websocket_loop(self):
        """Main WebSocket loop with reconnection"""
        ws_url = self._get_websocket_url()
        
        while self._running:
            try:
                self._logger.info(f"Connecting to {ws_url}")
                
                async with websockets.connect(ws_url) as ws:
                    self._ws = ws
                    self._logger.info("Connected to WebSocket")
                    
                    # Subscribe to tickers
                    await self._subscribe(ws)
                    
                    # Process messages
                    async for message in ws:
                        if not self._running:
                            break
                        
                        await self._process_message(message)
                
            except websockets.exceptions.ConnectionClosed:
                if self._running:
                    self._logger.warning(f"Connection closed, reconnecting in {self.RECONNECT_DELAY} sec")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    break
            
            except Exception as e:
                if self._running:
                    self._logger.error(f"WebSocket error: {e}")
                    self._logger.info(f"Reconnecting in {self.RECONNECT_DELAY} sec")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    break
        
        self._logger.info("WebSocket loop ended")
    
    async def _process_message(self, message: str):
        """
        Process message from WebSocket
        
        Args:
            message: Raw message
        """
        try:
            # Parse message and extract tickers
            tickers = self._parse_message(message)
            
            if not tickers:
                return
            
            redis = await get_redis()
            if not redis:
                return
            
            # Statistics
            updated_count = 0
            skipped_not_in_map = 0
            skipped_not_tracked = 0
            skipped_zero_price = 0
            skipped_wrong_priority = 0
            current_time = asyncio.get_event_loop().time()
            total_tickers = len(tickers)
            
            # Get extractor functions
            symbol_extractor = self._get_symbol_extractor()
            price_extractor = self._get_price_extractor()
            price_change_extractor = self._get_price_change_extractor()
            volume_extractor = self._get_volume_extractor()
            
            # Process each ticker
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
            
            # Log statistics periodically
            should_log = (current_time - self._last_log_time >= self.LOG_INTERVAL)
            
            if should_log:
                self._last_log_time = current_time
                
                # Clean old entries from _coins_with_updates (older than LOG_INTERVAL seconds)
                coins_to_remove = [
                    coin_id for coin_id, update_time in self._last_update_time.items()
                    if current_time - update_time > self.LOG_INTERVAL
                ]
                for coin_id in coins_to_remove:
                    self._coins_with_updates.discard(coin_id)
                
                # Detailed statistics for diagnostics
                coins_with_source = len([c for c in self._tracked_coins 
                                        if coin_registry.get_coin(c) and self._source in coin_registry.get_coin(c).external_ids])
                coins_not_in_source = len(self._tracked_coins) - coins_with_source
                
                self._logger.info(f"Updated prices: {updated_count} coins out of {total_tickers} tickers in this message")
                self._logger.info(f"Message statistics: skipped (not in mapping: {skipped_not_in_map}, not tracked: {skipped_not_tracked}, not priority {self._source}: {skipped_wrong_priority}, price=0: {skipped_zero_price})")
                self._logger.info(f"Total tracking: {len(self._tracked_coins)} coins | In {self._source}: {coins_with_source} | Not in {self._source}: {coins_not_in_source}")
                self._logger.info(f"Unique coins with updates in last {self.LOG_INTERVAL} sec: {len(self._coins_with_updates)}")
                
        except Exception as e:
            self._logger.error(f"Message processing error: {e}")