"""
Binance WebSocket Worker для получения цен в реальном времени

Использует !ticker@arr для получения всех тикеров одним потоком.
"""
import asyncio
import json
import websockets
from typing import Dict, Optional, Set
from pathlib import Path

from app.core.redis_client import get_redis
from app.core.coin_registry import coin_registry
from app.utils.formatters import get_price_decimals


class BinanceWebSocketWorker:
    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/!ticker@arr"
    RECONNECT_DELAY = 5  # Секунд до переподключения
    PRICE_UPDATE_INTERVAL = 0.1  # Обновляем кэш каждые 100ms (при получении данных)
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._tracked_coins: Set[str] = set()  # Множество внутренних ID из конфига
        self._last_update_time: Dict[str, float] = {}  # Для отслеживания частоты обновлений
        self._coins_with_updates: Set[str] = set()  # Множество монет, которые получили обновления за последний период
        
    def _load_coins_config(self) -> list[str]:
        try:
            # Получаем все монеты с Binance маппингом
            coins = coin_registry.get_coins_by_source("binance")
            coin_ids = [coin.id for coin in coins]
            
            print(f"[BinanceWebSocket] Загружено {len(coin_ids)} монет с Binance из реестра")
            return coin_ids
        except Exception as e:
            print(f"[BinanceWebSocket] Ошибка загрузки монет из реестра: {e}")
            return []
    
    
    async def start(self):
        if self._running:
            print("[BinanceWebSocket] Уже запущен")
            return
        
        self._running = True
        
        # Загружаем список монет из конфига
        config_coins = self._load_coins_config()
        self._tracked_coins = set(config_coins)
        
        if not self._tracked_coins:
            print("[BinanceWebSocket] ⚠️ Нет монет для отслеживания, WebSocket не запущен")
            self._running = False
            return
        
        # Определяем, какие монеты есть в Binance
        coins_in_binance = []
        coins_not_in_binance = []
        for coin_id in self._tracked_coins:
            coin = coin_registry.get_coin(coin_id)
            if coin and "binance" in coin.external_ids:
                coins_in_binance.append(coin_id)
            else:
                coins_not_in_binance.append(coin_id)
        
        print(f"[BinanceWebSocket] 🚀 Запуск WebSocket worker для {len(self._tracked_coins)} монет...")
        print(f"[BinanceWebSocket] 📈 Отслеживаем {len(self._tracked_coins)} монет | В Binance: {len(coins_in_binance)} | Не в Binance: {len(coins_not_in_binance)}")
        
        # Запускаем WebSocket loop в фоне
        self._task = asyncio.create_task(self._websocket_loop())
    
    async def stop(self):
        """Остановить WebSocket worker"""
        self._running = False
        
        if self._ws:
            await self._ws.close()
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        print("[BinanceWebSocket] ⏹️ WebSocket worker остановлен")
    
    async def close(self):
        await self.stop()
    
    async def _websocket_loop(self):
        while self._running:
            try:
                print(f"[BinanceWebSocket] 🔌 Подключение к {self.BINANCE_WS_URL}...")
                
                async with websockets.connect(self.BINANCE_WS_URL) as ws:
                    self._ws = ws
                    print("[BinanceWebSocket] ✅ Подключено к Binance WebSocket")
                    
                    async for message in ws:
                        if not self._running:
                            break
                        
                        await self._process_ticker_update(message)
                
            except websockets.exceptions.ConnectionClosed:
                if self._running:
                    print(f"[BinanceWebSocket] ⚠️ Соединение закрыто, переподключение через {self.RECONNECT_DELAY} сек...")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    break
            
            except Exception as e:
                if self._running:
                    print(f"[BinanceWebSocket] ❌ Ошибка WebSocket: {e}")
                    print(f"[BinanceWebSocket] Переподключение через {self.RECONNECT_DELAY} сек...")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    break
        
        print("[BinanceWebSocket] WebSocket loop завершен")
    
    async def _process_ticker_update(self, message: str):
        try:
            tickers = json.loads(message)
            
            if not isinstance(tickers, list):
                return
            
            redis = await get_redis()
            if not redis:
                return
            
            updated_count = 0
            skipped_not_in_map = 0
            skipped_not_tracked = 0
            skipped_zero_price = 0
            skipped_wrong_priority = 0
            current_time = asyncio.get_event_loop().time()
            total_tickers = len(tickers)
            
            # Обрабатываем каждый тикер
            for ticker in tickers:
                if not isinstance(ticker, dict):
                    continue
                
                symbol = ticker.get("s")  # Символ Binance (например, "BTCUSDT")
                if not symbol:
                    continue
                
                # Получаем внутренний ID монеты из CoinRegistry
                coin = coin_registry.find_coin_by_external_id("binance", symbol)
                if not coin:
                    skipped_not_in_map += 1
                    continue
                
                coin_id = coin.id  # Используем внутренний ID
                
                if coin_id not in self._tracked_coins:
                    skipped_not_tracked += 1
                    continue
                
                # Проверяем price_priority: Binance должен быть первым приоритетом
                # Если Binance не является первым приоритетом, не записываем цену в Redis
                price_priority = coin.price_priority
                if not price_priority or price_priority[0] != "binance":
                    skipped_wrong_priority += 1
                    continue
                
                price = float(ticker.get("c", 0))  # Текущая цена
                price_change_24h = float(ticker.get("P", 0))  # Изменение за 24ч в процентах
                volume_24h = float(ticker.get("v", 0))  # Объем за 24ч
                
                if price <= 0:
                    skipped_zero_price += 1
                    continue
                
                price_data = {
                    "price": price,
                    "percent_change_24h": price_change_24h,
                    "volume_24h": volume_24h,
                    "priceDecimals": get_price_decimals(price),
                }
                
                price_cache_key = f"coin_price:{coin_id}"
                
                try:
                    await redis.setex(
                        price_cache_key,
                        60,  # TTL в секундах
                        json.dumps(price_data)
                    )
                    
                    updated_count += 1
                    self._last_update_time[coin_id] = current_time
                    self._coins_with_updates.add(coin_id)  # Отслеживаем, какие монеты получили обновления
                    
                except Exception as e:
                    print(f"[BinanceWebSocket] Ошибка записи в Redis для {coin_id}: {e}")
            
            should_log = (
                current_time - getattr(self, '_last_log_time', 0) >= 5.0
            )
            
            if should_log:
                self._last_log_time = current_time
                
                # Очищаем старые записи из _coins_with_updates (старше 5 секунд)
                coins_to_remove = [
                    coin_id for coin_id, update_time in self._last_update_time.items()
                    if current_time - update_time > 5.0
                ]
                for coin_id in coins_to_remove:
                    self._coins_with_updates.discard(coin_id)
                
                if should_log:
                    # Детальная статистика для диагностики
                    coins_with_binance = len([c for c in self._tracked_coins 
                                             if coin_registry.get_coin(c) and "binance" in coin_registry.get_coin(c).external_ids])
                    coins_not_in_binance = len(self._tracked_coins) - coins_with_binance
                    
                    print(f"[BinanceWebSocket] 💰 Обновлено цен: {updated_count} монет из {total_tickers} тикеров в этом сообщении")
                    print(f"[BinanceWebSocket] 📊 Статистика сообщения: пропущено (нет в маппинге: {skipped_not_in_map}, не отслеживаем: {skipped_not_tracked}, не приоритет Binance: {skipped_wrong_priority}, цена=0: {skipped_zero_price})")
                    print(f"[BinanceWebSocket] 📈 Всего отслеживаем: {len(self._tracked_coins)} монет | В Binance: {coins_with_binance} | Не в Binance: {coins_not_in_binance}")
                    print(f"[BinanceWebSocket] ✅ Уникальных монет с обновлениями за последние 5 сек: {len(self._coins_with_updates)}")
                    
        except Exception as e:
            print(f"[BinanceWebSocket] Ошибка обработки сообщения: {e}")

# Глобальный экземпляр
binance_websocket_worker = BinanceWebSocketWorker()

