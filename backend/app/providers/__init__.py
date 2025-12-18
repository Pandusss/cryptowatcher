"""
Data providers for cryptocurrencies

Each provider is an independent module implementing an interface for data retrieval.
"""

from .base_adapters import BasePriceAdapter, BaseChartAdapter
from .base_websocket import BaseWebSocketWorker

# Price adapters
from .binance_price import binance_price_adapter
from .okx_price import okx_price_adapter
from .mexc_price import mexc_price_adapter

# Chart adapters
from .binance_chart import binance_chart_adapter
from .okx_chart import okx_chart_adapter
from .mexc_chart import mexc_chart_adapter

# WebSocket workers
from .binance_websocket import binance_websocket_worker
from .okx_websocket import okx_websocket_worker
from .mexc_websocket import mexc_websocket_worker

__all__ = [
    "BasePriceAdapter",
    "BaseChartAdapter",
    "BaseWebSocketWorker",
    "binance_price_adapter",
    "okx_price_adapter",
    "mexc_price_adapter",
    "binance_chart_adapter",
    "okx_chart_adapter",
    "mexc_chart_adapter",
    "binance_websocket_worker",
    "okx_websocket_worker",
    "mexc_websocket_worker",
]
