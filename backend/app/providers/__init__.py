"""
Data providers for cryptocurrencies

Each provider is an independent module implementing an interface for data retrieval.

Structure:
- cex/ - Centralized exchanges (Binance, OKX, MEXC)
- dex/ - Decentralized exchanges / Aggregators (CoinGecko)
"""

from .base_adapters import BasePriceAdapter, BaseChartAdapter
from .base_websocket import BaseWebSocketWorker

# Static data provider (stays in root)
from .coingecko_static import coingecko_static_adapter

# CEX providers
from .cex import (
    binance_price_adapter,
    okx_price_adapter,
    mexc_price_adapter,
    binance_chart_adapter,
    okx_chart_adapter,
    mexc_chart_adapter,
    binance_websocket_worker,
    okx_websocket_worker,
    mexc_websocket_worker,
)

# DEX providers
from .dex import (
    coingecko_price_adapter,
    coingecko_chart_adapter,
    coingecko_price_updater,
)

__all__ = [
    "BasePriceAdapter",
    "BaseChartAdapter",
    "BaseWebSocketWorker",
    "coingecko_static_adapter",
    "binance_price_adapter",
    "okx_price_adapter",
    "mexc_price_adapter",
    "binance_chart_adapter",
    "okx_chart_adapter",
    "mexc_chart_adapter",
    "binance_websocket_worker",
    "okx_websocket_worker",
    "mexc_websocket_worker",
    "coingecko_price_adapter",
    "coingecko_chart_adapter",
    "coingecko_price_updater",
]
