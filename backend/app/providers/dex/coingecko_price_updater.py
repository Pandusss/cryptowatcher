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
from app.core.config import settings

logger = logging.getLogger(__name__)


class CoinGeckoPriceUpdater:
    """Background service for updating CoinGecko prices"""

    LOG_INTERVAL = 60  # Log statistics every 60 seconds

    def __init__(self):
        self.running = False
        self._task: asyncio.Task = None
        self._tracked_coins: List[str] = []
        self._last_log_time: float = 0.0
        self._update_count: int = 0
        self._error_count: int = 0

    @property
    def update_interval(self) -> int:
        return settings.COINGECKO_UPDATE_INTERVAL

    def _load_tracked_coins(self) -> List[str]:
        """Load list of CoinGecko IDs that should be tracked."""
        tracked = []
        all_coins = coin_registry.get_all_coins(enabled_only=True)

        for coin in all_coins:
            coingecko_id = coin.external_ids.get("coingecko")
            if not coingecko_id:
                continue
            if "coingecko" not in coin.price_priority:
                continue
            tracked.append(coingecko_id)

        return tracked

    async def start(self):
        """Start the price updater"""
        if self.running:
            logger.warning("CoinGecko price updater already running")
            return

        self._tracked_coins = self._load_tracked_coins()

        if not self._tracked_coins:
            logger.warning("No coins to track via CoinGecko, updater not started")
            return

        self.running = True
        logger.info(f"Starting CoinGecko price updater for {len(self._tracked_coins)} coins")
        logger.info(f"Update interval: {self.update_interval} seconds")

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
                # Reload tracked coins periodically (in case config changed)
                self._tracked_coins = self._load_tracked_coins()

                if not self._tracked_coins:
                    logger.warning("No coins to track, waiting...")
                    await asyncio.sleep(self.update_interval)
                    continue

                start_time = asyncio.get_event_loop().time()

                try:
                    prices = await coingecko_price_adapter.get_prices(self._tracked_coins)

                    success_count = len(prices)
                    failed_count = len(self._tracked_coins) - success_count

                    self._update_count += success_count
                    if failed_count > 0:
                        self._error_count += failed_count

                    current_time = asyncio.get_event_loop().time()
                    should_log = (current_time - self._last_log_time >= self.LOG_INTERVAL)

                    if should_log:
                        self._last_log_time = current_time
                        logger.info(
                            f"CoinGecko update: {success_count}/{len(self._tracked_coins)} coins. "
                            f"Total: {self._update_count}, Errors: {self._error_count}"
                        )
                    else:
                        logger.debug(
                            f"Updated {success_count}/{len(self._tracked_coins)} prices"
                        )

                except Exception as e:
                    self._error_count += len(self._tracked_coins)
                    logger.error(f"Error updating CoinGecko prices: {e}")

                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, self.update_interval - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"Price update took {elapsed:.2f}s, longer than interval {self.update_interval}s")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in update loop: {e}")
                await asyncio.sleep(self.update_interval)

        logger.info("CoinGecko price update loop ended")


# Global instance
coingecko_price_updater = CoinGeckoPriceUpdater()
