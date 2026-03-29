"""
Binance WebSocket Worker for real-time price updates

Uses combined streams to subscribe only to tracked coins.
"""
import json
from typing import Dict, Optional, Callable
import websockets

from app.providers.base_websocket import BaseWebSocketWorker
from app.core.coin_registry import coin_registry


class BinanceWebSocketWorker(BaseWebSocketWorker):
    """WebSocket worker for price updates from Binance"""

    BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream?streams="

    def __init__(self):
        super().__init__(source="binance")

    def _get_websocket_url(self) -> str:
        """Build combined streams URL for tracked coins only"""
        streams = []
        for coin_id in self._tracked_coins:
            coin = coin_registry.get_coin(coin_id)
            if coin:
                binance_symbol = coin.external_ids.get("binance")
                if binance_symbol:
                    streams.append(f"{binance_symbol.lower()}@ticker")

        if not streams:
            self._logger.warning("No Binance symbols found for tracked coins")
            return f"{self.BINANCE_WS_BASE}btcusdt@ticker"

        self._logger.info(f"Subscribing to {len(streams)} Binance streams")
        return f"{self.BINANCE_WS_BASE}{'/'.join(streams)}"

    async def _subscribe(self, ws: websockets.WebSocketClientProtocol):
        """
        No explicit subscription needed for combined streams.
        """
        pass

    def _parse_message(self, message: str) -> Optional[list]:
        """
        Parse combined stream message from Binance.

        Combined stream format: {"stream": "btcusdt@ticker", "data": {ticker}}
        """
        try:
            parsed = json.loads(message)

            if isinstance(parsed, dict) and "data" in parsed:
                return [parsed["data"]]

            if isinstance(parsed, list):
                return parsed

            return None

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

# Global instance
binance_websocket_worker = BinanceWebSocketWorker()
