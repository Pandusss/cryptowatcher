"""
Quick CoinGecko service for bot commands
Searches coins by symbol and fetches price/chart data
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from app.providers.coingecko_client import CoinGeckoClient
from app.core.coin_registry import coin_registry

logger = logging.getLogger(__name__)

# Base parameters for /coins/markets endpoint
MARKETS_BASE_PARAMS = {
    "vs_currency": "usd",
    "order": "market_cap_desc",
    "per_page": 1,
    "page": 1,
    "sparkline": False,
}


class CoinGeckoQuickService:
    """Quick service for searching and fetching coin data from CoinGecko"""

    def __init__(self):
        self.client = CoinGeckoClient()

    async def search_coin_with_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Search for a coin by symbol and return info + price in a single API call.

        For coins in coin_registry this is ONE /coins/markets request instead of two.
        Returns dict with id, name, symbol, thumb, large, price, percent_change_24h,
        market_cap, volume_24h, high_24h, low_24h — or None.
        """
        symbol_upper = symbol.upper()

        # 1. Check registry first
        coin_config = coin_registry.find_coin_by_symbol(symbol_upper, enabled_only=True)
        if coin_config:
            coingecko_id = coin_config.external_ids.get("coingecko")
            if coingecko_id:
                try:
                    response = await self.client.get(
                        "/coins/markets",
                        params={**MARKETS_BASE_PARAMS, "ids": coingecko_id}
                    )
                    if response and len(response) > 0:
                        d = response[0]
                        price = float(d.get("current_price", 0))
                        if price > 0:
                            return {
                                "id": coingecko_id,
                                "name": coin_config.name,
                                "symbol": coin_config.symbol.upper(),
                                "thumb": d.get("image", ""),
                                "large": d.get("image", ""),
                                "price": price,
                                "percent_change_24h": float(d.get("price_change_percentage_24h", 0)),
                                "market_cap": d.get("market_cap"),
                                "volume_24h": d.get("total_volume"),
                                "high_24h": d.get("high_24h"),
                                "low_24h": d.get("low_24h"),
                            }
                except Exception:
                    logger.exception(f"Failed to get coin from markets for {coingecko_id}")

        # 2. Fallback: CoinGecko search API → then /coins/markets for price
        try:
            response = await self.client.get(
                "/search",
                params={"query": symbol_upper}
            )
            if not response or "coins" not in response:
                return None

            coins = response.get("coins", [])
            if not coins:
                return None

            # Find exact symbol match
            matched = None
            for coin in coins:
                if coin.get("symbol", "").upper() == symbol_upper:
                    matched = coin
                    break
            if not matched:
                matched = coins[0]

            coin_id = matched.get("id")
            if not coin_id:
                return None

            # Fetch price data
            price_data = await self._fetch_price(coin_id)
            if not price_data:
                return None

            return {
                "id": coin_id,
                "name": matched.get("name"),
                "symbol": matched.get("symbol", "").upper(),
                "thumb": matched.get("thumb"),
                "large": matched.get("large"),
                **price_data,
            }
        except Exception:
            logger.exception(f"Error searching coin {symbol}")
            return None

    async def _fetch_price(self, coin_id: str) -> Optional[Dict[str, Any]]:
        """Fetch price data for a coin_id from /coins/markets or /simple/price."""
        try:
            response = await self.client.get(
                "/coins/markets",
                params={**MARKETS_BASE_PARAMS, "ids": coin_id}
            )
            if response and len(response) > 0:
                d = response[0]
                price = float(d.get("current_price", 0))
                if price > 0:
                    return {
                        "price": price,
                        "percent_change_24h": float(d.get("price_change_percentage_24h", 0)),
                        "market_cap": d.get("market_cap"),
                        "volume_24h": d.get("total_volume"),
                        "high_24h": d.get("high_24h"),
                        "low_24h": d.get("low_24h"),
                    }

            # Fallback to simple/price
            response_simple = await self.client.get(
                "/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_24hr_vol": "true",
                }
            )
            if not response_simple or coin_id not in response_simple:
                return None

            d = response_simple[coin_id]
            price = float(d.get("usd", 0))
            if price <= 0:
                return None

            return {
                "price": price,
                "percent_change_24h": float(d.get("usd_24h_change", 0)),
                "market_cap": d.get("usd_market_cap"),
                "volume_24h": d.get("usd_24h_vol"),
                "high_24h": d.get("usd_24h_high"),
                "low_24h": d.get("usd_24h_low"),
            }
        except Exception:
            logger.exception(f"Error fetching price for {coin_id}")
            return None

    async def get_coin_chart_data(self, coin_id: str, days: int = 7) -> Optional[List[Dict[str, Any]]]:
        """Get chart data for a coin."""
        try:
            response = await self.client.get(
                f"/coins/{coin_id}/market_chart",
                params={
                    "vs_currency": "usd",
                    "days": days,
                }
            )
            if not response or "prices" not in response:
                return None

            prices = response.get("prices", [])
            if not prices:
                return None

            return [
                {"timestamp": point[0], "price": float(point[1])}
                for point in prices
            ]
        except Exception:
            logger.exception(f"Error fetching chart data for {coin_id}")
            return None

    async def get_coin_full_data(self, symbol: str, days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Get full data for a coin: info + price (single API call) + chart data.

        Previously this made 3 sequential HTTP calls; now it's 1 + 1.
        """
        # Single call: coin info + price + image
        coin_data = await self.search_coin_with_price(symbol)
        if not coin_data:
            return None

        # Chart data
        chart_data = await self.get_coin_chart_data(coin_data["id"], days)
        if isinstance(chart_data, Exception):
            chart_data = None

        coin_data["chart_data"] = chart_data or []
        return coin_data


# Global instance
coingecko_quick = CoinGeckoQuickService()
