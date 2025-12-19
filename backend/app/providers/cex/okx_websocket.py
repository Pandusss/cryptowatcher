"""
OKX WebSocket Worker for getting real-time prices

Uses public tickers channel to get all tickers.
Updates Redis cache with coin_price:{coin_id} keys for compatibility.
"""
import json
from typing import Dict, Optional, Callable
import websockets

from app.providers.base_websocket import BaseWebSocketWorker
from app.core.coin_registry import coin_registry


class OKXWebSocketWorker(BaseWebSocketWorker):
    """WebSocket worker for getting prices from OKX"""
    
    OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
    MAX_SUBSCRIPTIONS_PER_REQUEST = 100  # OKX limit on number of subscriptions per request
    
    def __init__(self):
        super().__init__(source="okx")
    
    def _get_websocket_url(self) -> str:
        """Get URL for WebSocket connection"""
        return self.OKX_WS_URL
    
    async def _subscribe(self, ws: websockets.WebSocketClientProtocol):
        """
        Subscribe to OKX tickers
        
        OKX requires explicit subscription for each ticker.
        Format: {"op": "subscribe", "args": [{"channel": "tickers", "instId": "BTC-USDT"}, ...]}
        """
        # Get all OKX symbols for tracked coins
        okx_symbols = []
        for coin_id in self._tracked_coins:
            coin = coin_registry.get_coin(coin_id)
            if coin and "okx" in coin.external_ids:
                okx_symbols.append(coin.external_ids["okx"])
        
        if not okx_symbols:
            self._logger.warning("No OKX symbols to subscribe to")
            return
        
        # Subscribe in batches (OKX has limit on number of subscriptions per request)
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
            
            self._logger.info(f"Subscribed to {len(subscribe_args)} tickers (total: {total_subscribed}/{len(okx_symbols)})")
    
    def _parse_message(self, message: str) -> Optional[list]:
        """
        Parse message from OKX and extract tickers
        
        OKX sends data in format:
        - Subscription confirmation: {"event": "subscribe", "arg": {...}}
        - Ticker data: {"data": [{...}, {...}], "arg": {...}}
        """
        try:
            data = json.loads(message)
            
            # Handle subscription events
            if data.get("event") == "subscribe":
                channel_info = data.get('arg', {})
                self._logger.debug(f"Subscription confirmed: {channel_info}")
                return None
            
            # Handle ticker data
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
            
            return None
            
        except Exception as e:
            self._logger.error(f"Message parsing error: {e}", exc_info=True)
            return None
    
    def _get_symbol_extractor(self) -> Callable[[Dict], Optional[str]]:
        """Extract symbol from OKX ticker"""
        return lambda t: t.get("instId")
    
    def _get_price_extractor(self) -> Callable[[Dict], float]:
        """Extract price from OKX ticker"""
        return lambda t: float(t.get("last", 0))
    
    def _get_price_change_extractor(self) -> Callable[[Dict], float]:
        """
        Extract 24h price change from OKX ticker
        
        OKX doesn't provide percentage change directly,
        so we calculate it from current price and 24h open price
        """
        def extractor(t: Dict) -> float:
            price = float(t.get("last", 0))
            open_24h = float(t.get("open24h", 0))
            if open_24h > 0:
                return ((price - open_24h) / open_24h) * 100
            return 0.0
        
        return extractor
    
    def _get_volume_extractor(self) -> Callable[[Dict], float]:
        """Extract 24h volume from OKX ticker"""
        return lambda t: float(t.get("vol24h", 0))

okx_websocket_worker = OKXWebSocketWorker()