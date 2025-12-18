"""
MEXC WebSocket Worker for real-time price updates

Uses protobuf messages for miniTickers channel.
"""
import json
import asyncio
from typing import Dict, Optional, Callable, List
import websockets

from app.providers.base_websocket import BaseWebSocketWorker
from app.pb2 import PushDataV3ApiWrapper_pb2


class MEXCWebSocketWorker(BaseWebSocketWorker):
    """WebSocket worker for price updates from MEXC"""
    
    MEXC_WS_URL = "wss://wbs-api.mexc.com/ws"
    
    def __init__(self):
        super().__init__(source="mexc")
    
    def _get_websocket_url(self) -> str:
        """Get URL for WebSocket connection"""
        return self.MEXC_WS_URL
    
    async def _subscribe(self, ws: websockets.WebSocketClientProtocol):
        """
        Subscribe to all tickers via miniTickers channel.
        
        MEXC uses subscription with channel name "spot@public.miniTickers.v3.api.pb@UTC+3"
        """
        subscribe_msg = {
            "method": "SUBSCRIPTION",
            "params": ["spot@public.miniTickers.v3.api.pb@UTC+3"]
        }
        await ws.send(json.dumps(subscribe_msg))
        self._logger.info("Subscribed to MEXC miniTickers channel")
    
    def _parse_message(self, message: str) -> Optional[list]:
        """
        Parse message from MEXC and extract tickers.
        
        Messages can be:
        - Text JSON (ping/pong)
        - Binary protobuf (PushDataV3ApiWrapper)
        """
        # If message is string, it's JSON (ping/pong)
        if isinstance(message, str):
            if '"ping"' in message:
                # Handle ping (we'll respond in _process_message)
                return None
            # Could be other JSON messages, ignore
            return None
        
        # Binary message - parse protobuf
        try:
            data = PushDataV3ApiWrapper_pb2.PushDataV3ApiWrapper()
            data.ParseFromString(message)
            
            if data.HasField("publicMiniTickers"):
                tickers = []
                for ticker in data.publicMiniTickers.items:
                    # Convert protobuf message to dict
                    ticker_dict = {
                        "symbol": ticker.symbol,
                        "price": ticker.price,
                        "rate": ticker.rate,
                        "zonedRate": ticker.zonedRate,
                        "high": ticker.high,
                        "low": ticker.low,
                        "volume": ticker.volume,
                        "quantity": ticker.quantity,
                        "lastCloseRate": ticker.lastCloseRate,
                        "lastCloseZonedRate": ticker.lastCloseZonedRate,
                        "lastCloseHigh": ticker.lastCloseHigh,
                        "lastCloseLow": ticker.lastCloseLow,
                    }
                    tickers.append(ticker_dict)
                return tickers
            else:
                # Other message types not needed for price updates
                return None
                
        except Exception as e:
            self._logger.error(f"Protobuf parsing error: {e}", exc_info=True)
            return None
    
    async def _process_message(self, message: str):
        """
        Override to handle ping/pong messages before parsing.
        """
        # Handle ping messages (text JSON)
        if isinstance(message, str):
            try:
                data = json.loads(message)
                if "ping" in data:
                    # Respond with pong
                    if self._ws:
                        pong_msg = json.dumps({"pong": data["ping"]})
                        await self._ws.send(pong_msg)
                    return
            except json.JSONDecodeError:
                pass
        
        # Call parent method for ticker processing
        await super()._process_message(message)
    
    def _get_symbol_extractor(self) -> Callable[[Dict], Optional[str]]:
        """Extract symbol from MEXC ticker"""
        return lambda t: t.get("symbol")
    
    def _get_price_extractor(self) -> Callable[[Dict], float]:
        """Extract price from MEXC ticker"""
        return lambda t: float(t.get("price", 0))
    
    def _get_price_change_extractor(self) -> Callable[[Dict], float]:
        """Extract 24h price change from MEXC ticker"""
        return lambda t: float(t.get("rate", 0))
    
    def _get_volume_extractor(self) -> Callable[[Dict], float]:
        """Extract 24h volume from MEXC ticker"""
        return lambda t: float(t.get("volume", 0))


# Global instance
mexc_websocket_worker = MEXCWebSocketWorker()