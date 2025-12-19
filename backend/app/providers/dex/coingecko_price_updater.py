"""
CoinGecko Price Updater

Background service that periodically fetches prices from CoinGecko REST API
and updates Redis cache. Similar to WebSocket workers but uses HTTP polling.
"""
import asyncio
import logging
from typing import List, Dict

from app.providers.dex.coingecko_price import coingecko_price_adapter
from app.core.coin_registry import coin_registry

logger = logging.getLogger("CoinGeckoPriceUpdater")


class CoinGeckoPriceUpdater:
    """Background service for updating CoinGecko prices"""
    
    UPDATE_INTERVAL = 3  # Update every 3 seconds
    LOG_INTERVAL = 60  # Log statistics every 60 seconds
    
    def __init__(self):
        self.running = False
        self._task: asyncio.Task = None
        self._tracked_coins: List[str] = []  # List of CoinGecko IDs
        self._last_log_time: float = 0.0
        self._update_count: int = 0
        self._error_count: int = 0
    
    def _load_tracked_coins(self) -> List[str]:
        """
        Load list of CoinGecko IDs that should be tracked:
        - Must have 'coingecko' in external_ids
        - Must have 'coingecko' in price_priority
        """
        tracked = []
        all_coins = coin_registry.get_all_coins(enabled_only=True)
        
        for coin in all_coins:
            coingecko_id = coin.external_ids.get("coingecko")
            if not coingecko_id:
                continue
            
            # Check if coingecko is in price_priority
            if "coingecko" not in coin.price_priority:
                continue
            
            tracked.append(coingecko_id)
        
        return tracked
    
    async def start(self):
        """Start the price updater"""
        if self.running:
            logger.warning("CoinGecko price updater already running")
            return
        
        # Load tracked coins
        self._tracked_coins = self._load_tracked_coins()
        
        if not self._tracked_coins:
            logger.warning("No coins to track via CoinGecko, updater not started")
            return
        
        self.running = True
        logger.info(f"Starting CoinGecko price updater for {len(self._tracked_coins)} coins")
        logger.info(f"Update interval: {self.UPDATE_INTERVAL} seconds")
        logger.info(f"Tracked coins: {self._tracked_coins[:5]}{'...' if len(self._tracked_coins) > 5 else ''}")
        
        # Start background task
        self._task = asyncio.create_task(self._update_loop())
    
    async def stop(self):
        """Stop the price updater"""
        self.running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("CoinGecko price updater stopped")
    
    async def close(self):
        """Close the updater (alias for stop)"""
        await self.stop()
        await coingecko_price_adapter.close()
    
    async def _update_loop(self):
        """Main update loop"""
        while self.running:
            try:
                # Reload tracked coins (in case config changed)
                self._tracked_coins = self._load_tracked_coins()
                
                if not self._tracked_coins:
                    logger.warning("No coins to track, waiting...")
                    await asyncio.sleep(self.UPDATE_INTERVAL)
                    continue
                
                # Fetch prices for all tracked coins
                start_time = asyncio.get_event_loop().time()
                
                try:
                    # Use batch request to get all prices at once
                    logger.debug(f"Fetching prices for {len(self._tracked_coins)} coins from CoinGecko...")
                    prices = await coingecko_price_adapter.get_prices(self._tracked_coins)
                    
                    success_count = len(prices)
                    failed_count = len(self._tracked_coins) - success_count
                    
                    self._update_count += success_count
                    
                    if failed_count > 0:
                        self._error_count += failed_count
                    
                    # Log every update for visibility
                    current_time = asyncio.get_event_loop().time()
                    should_log = (current_time - self._last_log_time >= self.LOG_INTERVAL)
                    
                    if should_log:
                        self._last_log_time = current_time
                        logger.info(
                            f"CoinGecko price update: {success_count}/{len(self._tracked_coins)} coins updated. "
                            f"Total updates: {self._update_count}, Errors: {self._error_count}"
                        )
                    
                    # Always log update activity (INFO level for visibility)
                    logger.info(
                        f"[CoinGecko] Updated {success_count}/{len(self._tracked_coins)} prices. "
                        f"Sample: {list(prices.keys())[:3] if prices else 'none'}"
                    )
                    
                except Exception as e:
                    self._error_count += len(self._tracked_coins)
                    logger.error(f"Error updating CoinGecko prices: {e}")
                
                # Wait before next update
                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, self.UPDATE_INTERVAL - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    # If update took longer than interval, log warning
                    logger.warning(f"Price update took {elapsed:.2f}s, longer than interval {self.UPDATE_INTERVAL}s")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in update loop: {e}")
                await asyncio.sleep(self.UPDATE_INTERVAL)
        
        logger.info("CoinGecko price update loop ended")


# Global instance
coingecko_price_updater = CoinGeckoPriceUpdater()

