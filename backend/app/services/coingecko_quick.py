"""
Quick CoinGecko service for bot commands
Searches coins by symbol and fetches price/chart data
"""
import logging
from typing import Optional, Dict, Any, List
from app.providers.coingecko_client import CoinGeckoClient

logger = logging.getLogger("CoinGeckoQuick")


class CoinGeckoQuickService:
    """Quick service for searching and fetching coin data from CoinGecko"""
    
    def __init__(self):
        self.client = CoinGeckoClient()
    
    async def search_coin(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Search for a coin by symbol (e.g., 'ETH', 'BTC')
        
        Returns:
            Dict with coin_id, name, symbol, etc. or None if not found
        """
        try:
            # CoinGecko search endpoint
            response = await self.client.get(
                "/search",
                params={"query": symbol.upper()}
            )
            
            if not response or "coins" not in response:
                return None
            
            coins = response.get("coins", [])
            if not coins:
                return None
            
            # Find exact symbol match (case-insensitive)
            for coin in coins:
                if coin.get("symbol", "").upper() == symbol.upper():
                    return {
                        "id": coin.get("id"),
                        "name": coin.get("name"),
                        "symbol": coin.get("symbol", "").upper(),
                        "thumb": coin.get("thumb"),
                        "large": coin.get("large"),
                    }
            
            # If no exact match, return first result
            first_coin = coins[0]
            return {
                "id": first_coin.get("id"),
                "name": first_coin.get("name"),
                "symbol": first_coin.get("symbol", "").upper(),
                "thumb": first_coin.get("thumb"),
                "large": first_coin.get("large"),
            }
            
        except Exception as e:
            logger.error(f"Error searching coin {symbol}: {e}")
            return None
    
    async def get_coin_price(self, coin_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current price and 24h change for a coin
        
        Returns:
            Dict with price, percent_change_24h, market_cap, volume_24h, high_24h, low_24h
        """
        try:
            # Use /coins/markets endpoint to get more data including market cap, high, low
            response = await self.client.get(
                "/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": coin_id,
                    "order": "market_cap_desc",
                    "per_page": 1,
                    "page": 1,
                    "sparkline": False,
                }
            )
            
            if not response or len(response) == 0:
                # Fallback to simple/price if markets endpoint fails
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
                
                coin_data = response_simple[coin_id]
                price = coin_data.get("usd", 0)
                
                if price <= 0:
                    return None
                
                return {
                    "price": float(price),
                    "percent_change_24h": float(coin_data.get("usd_24h_change", 0)),
                    "market_cap": coin_data.get("usd_market_cap"),
                    "volume_24h": coin_data.get("usd_24h_vol"),
                    "high_24h": coin_data.get("usd_24h_high"),
                    "low_24h": coin_data.get("usd_24h_low"),
                }
            
            coin_data = response[0]  # First (and only) result
            
            return {
                "price": float(coin_data.get("current_price", 0)),
                "percent_change_24h": float(coin_data.get("price_change_percentage_24h", 0)),
                "market_cap": coin_data.get("market_cap"),
                "volume_24h": coin_data.get("total_volume"),
                "high_24h": coin_data.get("high_24h"),
                "low_24h": coin_data.get("low_24h"),
            }
            
        except Exception as e:
            logger.error(f"Error fetching price for {coin_id}: {e}")
            return None
    
    async def get_coin_chart_data(self, coin_id: str, days: int = 7) -> Optional[List[Dict[str, Any]]]:
        """
        Get chart data for a coin
        
        Args:
            coin_id: CoinGecko coin ID
            days: Number of days (1, 7, 30, 365)
            
        Returns:
            List of dicts with timestamp and price
        """
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
            
            # Convert to list of dicts
            chart_data = []
            for point in prices:
                chart_data.append({
                    "timestamp": point[0],  # milliseconds
                    "price": float(point[1]),
                })
            
            return chart_data
            
        except Exception as e:
            logger.error(f"Error fetching chart data for {coin_id}: {e}")
            return None
    
    async def get_coin_full_data(self, symbol: str, days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Get full data for a coin: info, price, and chart
        
        Returns:
            Dict with coin info, price data, and chart data
        """
        # Search for coin
        coin_info = await self.search_coin(symbol)
        if not coin_info:
            return None
        
        coin_id = coin_info["id"]
        
        # Get price and chart in parallel
        import asyncio
        price_data, chart_data = await asyncio.gather(
            self.get_coin_price(coin_id),
            self.get_coin_chart_data(coin_id, days),
            return_exceptions=True
        )
        
        if isinstance(price_data, Exception):
            price_data = None
        if isinstance(chart_data, Exception):
            chart_data = None
        
        if not price_data:
            return None
        
        result = {
            **coin_info,
            "price": price_data["price"],
            "percent_change_24h": price_data["percent_change_24h"],
            "chart_data": chart_data or [],
        }
        
        # Add optional market data if available
        if "market_cap" in price_data:
            result["market_cap"] = price_data["market_cap"]
        if "volume_24h" in price_data:
            result["volume_24h"] = price_data["volume_24h"]
        if "high_24h" in price_data:
            result["high_24h"] = price_data["high_24h"]
        if "low_24h" in price_data:
            result["low_24h"] = price_data["low_24h"]
        
        return result


# Global instance
coingecko_quick = CoinGeckoQuickService()

