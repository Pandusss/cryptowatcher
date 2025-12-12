"""
OKX WebSocket Worker для получения цен в реальном времени

Использует публичный канал tickers для получения всех тикеров.
Обновляет Redis кэш с ключами coin_price:{coin_id} для совместимости.
"""
import asyncio
import json
import websockets
from typing import Dict, Optional, Set
from pathlib import Path

from app.core.redis_client import get_redis
from app.core.coin_registry import coin_registry
from app.utils.formatters import get_price_decimals


class OKXWebSocketWorker:

    OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
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
            # Получаем все монеты с OKX маппингом
            coins = coin_registry.get_coins_by_source("okx")
            coin_ids = [coin.id for coin in coins]
            
            print(f"[OKXWebSocket] Загружено {len(coin_ids)} монет с OKX из реестра")
            return coin_ids
        except Exception as e:
            print(f"[OKXWebSocket] Ошибка загрузки монет из реестра: {e}")
            return []
    
    
    async def start(self):
        if self._running:
            print("[OKXWebSocket] Уже запущен")
            return
        
        self._running = True
        
        # Загружаем список монет из конфига
        config_coins = self._load_coins_config()
        self._tracked_coins = set(config_coins)
        
        if not self._tracked_coins:
            print("[OKXWebSocket] ⚠️ Нет монет для отслеживания, WebSocket не запущен")
            self._running = False
            return
        
        # Определяем, какие монеты есть в OKX
        coins_in_okx = []
        coins_not_in_okx = []
        for coin_id in self._tracked_coins:
            coin = coin_registry.get_coin(coin_id)
            if coin and "okx" in coin.external_ids:
                coins_in_okx.append(coin_id)
            else:
                coins_not_in_okx.append(coin_id)
        
        print(f"[OKXWebSocket] 🚀 Запуск WebSocket worker для {len(self._tracked_coins)} монет...")
        print(f"[OKXWebSocket] 📈 Отслеживаем {len(self._tracked_coins)} монет | В OKX: {len(coins_in_okx)} | Не в OKX: {len(coins_not_in_okx)}")
        
        # Запускаем WebSocket loop в фоне
        self._task = asyncio.create_task(self._websocket_loop())
    
    async def stop(self):
        self._running = False
        
        if self._ws:
            await self._ws.close()
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        print("[OKXWebSocket] ⏹️ WebSocket worker остановлен")
    
    async def close(self):
        await self.stop()
    
    async def _websocket_loop(self):
        while self._running:
            try:
                print(f"[OKXWebSocket] 🔌 Подключение к {self.OKX_WS_URL}...")
                
                async with websockets.connect(self.OKX_WS_URL) as ws:
                    self._ws = ws
                    print("[OKXWebSocket] ✅ Подключено к OKX WebSocket")
                    
                    # OKX использует формат: {"op": "subscribe", "args": [{"channel": "tickers", "instId": "BTC-USDT"}]}
                    # Для всех тикеров можно подписаться на канал без instId или использовать специальный формат
                    # Но OKX не поддерживает получение всех тикеров одним запросом как Binance
                    # Нужно подписаться на каждый тикер отдельно или использовать другой подход
                    
                    okx_symbols = []
                    for coin_id in self._tracked_coins:
                        coin = coin_registry.get_coin(coin_id)
                        if coin and "okx" in coin.external_ids:
                            okx_symbols.append(coin.external_ids["okx"])
                    
                    if okx_symbols:
                        # Подписываемся на каждый тикер отдельно
                        # OKX позволяет подписаться на несколько тикеров одним запросом
                        # Формат: {"op": "subscribe", "args": [{"channel": "tickers", "instId": "BTC-USDT"}, ...]}
                        subscribe_args = [
                            {"channel": "tickers", "instId": symbol}
                            for symbol in okx_symbols[:100]
                        ]
                        
                        subscribe_msg = {
                            "op": "subscribe",
                            "args": subscribe_args
                        }
                        
                        await ws.send(json.dumps(subscribe_msg))
                        print(f"[OKXWebSocket] 📡 Подписано на {len(subscribe_args)} тикеров")
                    
                    async for message in ws:
                        if not self._running:
                            break
                        
                        await self._process_message(message)
                
            except websockets.exceptions.ConnectionClosed:
                if self._running:
                    print(f"[OKXWebSocket] ⚠️ Соединение закрыто, переподключение через {self.RECONNECT_DELAY} сек...")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    break
            
            except Exception as e:
                if self._running:
                    print(f"[OKXWebSocket] ❌ Ошибка WebSocket: {e}")
                    print(f"[OKXWebSocket] Переподключение через {self.RECONNECT_DELAY} сек...")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    break
        
        print("[OKXWebSocket] WebSocket loop завершен")
    
    async def _process_message(self, message: str):

        try:
            data = json.loads(message)
            
            # Обрабатываем события подписки
            if data.get("event") == "subscribe":
                print(f"[OKXWebSocket] ✅ Подписка подтверждена: {data.get('arg', {})}")
                return
            
            # Обрабатываем данные тикеров
            if "data" in data and isinstance(data["data"], list):
                tickers = data["data"]
                
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
                
                for ticker in tickers:
                    if not isinstance(ticker, dict):
                        continue
                    
                    # OKX формат: instId = "BTC-USDT", last = цена, open24h = цена 24ч назад, vol24h = объем
                    inst_id = ticker.get("instId") 
                    if not inst_id:
                        continue
                    
                    coin = coin_registry.find_coin_by_external_id("okx", inst_id)
                    if not coin:
                        skipped_not_in_map += 1
                        continue
                    
                    coin_id = coin.id
                    
                    if coin_id not in self._tracked_coins:
                        skipped_not_tracked += 1
                        continue
                    
                    # Проверяем price_priority: OKX должен быть первым приоритетом
                    # Если OKX не является первым приоритетом, не записываем цену в Redis
                    price_priority = coin.price_priority
                    if not price_priority or price_priority[0] != "okx":
                        skipped_wrong_priority += 1
                        continue
                    
                    price = float(ticker.get("last", 0))  
                    
                    # Вычисляем изменение за 24ч в процентах
                    open_24h = float(ticker.get("open24h", 0))
                    if open_24h > 0:
                        price_change_24h = ((price - open_24h) / open_24h) * 100
                    else:
                        price_change_24h = 0
                    
                    volume_24h = float(ticker.get("vol24h", 0))  # Объем за 24ч
                    
                    if price <= 0:
                        skipped_zero_price += 1
                        continue
                    
                    # Формируем данные для кэша
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
                            60, 
                            json.dumps(price_data)
                        )
                        
                        updated_count += 1
                        self._last_update_time[coin_id] = current_time
                        self._coins_with_updates.add(coin_id) 
                        
                    except Exception as e:
                        print(f"[OKXWebSocket] Ошибка записи в Redis для {coin_id}: {e}")
                
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
                        coins_with_okx = len([c for c in self._tracked_coins 
                                             if coin_registry.get_coin(c) and "okx" in coin_registry.get_coin(c).external_ids])
                        coins_not_in_okx = len(self._tracked_coins) - coins_with_okx
                        
                        print(f"[OKXWebSocket] 💰 Обновлено цен: {updated_count} монет из {total_tickers} тикеров в этом сообщении")
                        print(f"[OKXWebSocket] 📊 Статистика сообщения: пропущено (нет в маппинге: {skipped_not_in_map}, не отслеживаем: {skipped_not_tracked}, не приоритет OKX: {skipped_wrong_priority}, цена=0: {skipped_zero_price})")
                        print(f"[OKXWebSocket] 📈 Всего отслеживаем: {len(self._tracked_coins)} монет | В OKX: {coins_with_okx} | Не в OKX: {coins_not_in_okx}")
                        print(f"[OKXWebSocket] ✅ Уникальных монет с обновлениями за последние 5 сек: {len(self._coins_with_updates)}")
                    
        except Exception as e:
            print(f"[OKXWebSocket] Ошибка обработки сообщения: {e}")
            import traceback
            traceback.print_exc()

okx_websocket_worker = OKXWebSocketWorker()