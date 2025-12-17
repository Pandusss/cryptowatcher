"""
OKX WebSocket Worker для получения цен в реальном времени

Использует публичный канал tickers для получения всех тикеров.
Обновляет Redis кэш с ключами coin_price:{coin_id} для совместимости.
"""
import json
from typing import Dict, Optional, Callable
import websockets

from app.providers.base_websocket import BaseWebSocketWorker
from app.core.coin_registry import coin_registry


class OKXWebSocketWorker(BaseWebSocketWorker):
    """WebSocket worker для получения цен с OKX"""
    
    OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
    MAX_SUBSCRIPTIONS_PER_REQUEST = 100  # OKX лимит на количество подписок в одном запросе
    
    def __init__(self):
        super().__init__(source="okx")
    
    def _get_websocket_url(self) -> str:
        """Получить URL для WebSocket подключения"""
        return self.OKX_WS_URL
    
    async def _subscribe(self, ws: websockets.WebSocketClientProtocol):
        """
        Подписаться на тикеры OKX
        
        OKX требует явной подписки на каждый тикер.
        Формат: {"op": "subscribe", "args": [{"channel": "tickers", "instId": "BTC-USDT"}, ...]}
        """
        # Получаем все символы OKX для отслеживаемых монет
        okx_symbols = []
        for coin_id in self._tracked_coins:
            coin = coin_registry.get_coin(coin_id)
            if coin and "okx" in coin.external_ids:
                okx_symbols.append(coin.external_ids["okx"])
        
        if not okx_symbols:
            self._logger.warning("Нет символов OKX для подписки")
            return
        
        # Подписываемся батчами (OKX имеет лимит на количество подписок в одном запросе)
        total_subscribed = 0
        for i in range(0, len(okx_symbols), self.MAX_SUBSCRIPTIONS_PER_REQUEST):
            batch = okx_symbols[i:i + self.MAX_SUBSCRIPTIONS_PER_REQUEST]
            subscribe_args = [
                {"channel": "tickers", "instId": symbol}
                for symbol in batch
            ]
            
            subscribe_msg = {
                "op": "subscribe",
                "args": subscribe_args
            }
            
            await ws.send(json.dumps(subscribe_msg))
            total_subscribed += len(subscribe_args)
            
            self._logger.info(f"Подписано на {len(subscribe_args)} тикеров (всего: {total_subscribed}/{len(okx_symbols)})")
    
    def _parse_message(self, message: str) -> Optional[list]:
        """
        Распарсить сообщение от OKX и извлечь тикеры
        
        OKX отправляет данные в формате:
        - Подтверждение подписки: {"event": "subscribe", "arg": {...}}
        - Данные тикеров: {"data": [{...}, {...}], "arg": {...}}
        """
        try:
            data = json.loads(message)
            
            # Обрабатываем события подписки
            if data.get("event") == "subscribe":
                channel_info = data.get('arg', {})
                self._logger.debug(f"Подписка подтверждена: {channel_info}")
                return None
            
            # Обрабатываем данные тикеров
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
            
            return None
            
        except Exception as e:
            self._logger.error(f"Ошибка парсинга сообщения: {e}", exc_info=True)
            return None
    
    def _get_symbol_extractor(self) -> Callable[[Dict], Optional[str]]:
        """Извлечь символ из OKX тикера"""
        return lambda t: t.get("instId")
    
    def _get_price_extractor(self) -> Callable[[Dict], float]:
        """Извлечь цену из OKX тикера"""
        return lambda t: float(t.get("last", 0))
    
    def _get_price_change_extractor(self) -> Callable[[Dict], float]:
        """
        Извлечь изменение цены за 24ч из OKX тикера
        
        OKX не предоставляет процентное изменение напрямую,
        поэтому вычисляем его из текущей цены и цены открытия 24ч назад
        """
        def extractor(t: Dict) -> float:
            price = float(t.get("last", 0))
            open_24h = float(t.get("open24h", 0))
            if open_24h > 0:
                return ((price - open_24h) / open_24h) * 100
            return 0.0
        
        return extractor
    
    def _get_volume_extractor(self) -> Callable[[Dict], float]:
        """Извлечь объем за 24ч из OKX тикера"""
        return lambda t: float(t.get("vol24h", 0))

okx_websocket_worker = OKXWebSocketWorker()