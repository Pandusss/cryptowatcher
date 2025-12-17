"""
Binance WebSocket Worker for real-time price updates

Uses !ticker@arr to receive all tickers in one stream.
"""
import json
from typing import Dict, Optional, Callable
import websockets

from app.providers.base_websocket import BaseWebSocketWorker


class BinanceWebSocketWorker(BaseWebSocketWorker):
    """WebSocket worker for price updates from Binance"""
    
    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/!ticker@arr"
    
    def __init__(self):
        super().__init__(source="binance")
    
    def _get_websocket_url(self) -> str:
        """Get URL for WebSocket connection"""
        return self.BINANCE_WS_URL
    
    async def _subscribe(self, ws: websockets.WebSocketClientProtocol):
        """
        Binance does not require explicit subscription for !ticker@arr
        All tickers arrive automatically
        """
        pass
    
    def _parse_message(self, message: str) -> Optional[list]:
        """
        Parse the message from Binance and extract tickers.

        Binance sends an array of tickers in JSON format.
        """
        try:
            tickers = json.loads(message)
            
            if not isinstance(tickers, list):
                return None     
            
            return tickers
            
        except Exception:
            return None
    
    def _get_symbol_extractor(self) -> Callable[[Dict], Optional[str]]:
        """Extract symbol from Binance ticker"""
        return lambda t: t.get("s")
    
    def _get_price_extractor(self) -> Callable[[Dict], float]:
        """Extract price from Binance ticker"""
        return lambda t: float(t.get("c", 0))
    
    def _get_price_change_extractor(self) -> Callable[[Dict], float]:
        """Extract 24h price change from Binance ticker"""
        return lambda t: float(t.get("P", 0))
    
    def _get_volume_extractor(self) -> Callable[[Dict], float]:
        """Extract 24h volume from Binance ticker"""
        return lambda t: float(t.get("v", 0))

# Глобальный экземпляр
binance_websocket_worker = BinanceWebSocketWorker()


