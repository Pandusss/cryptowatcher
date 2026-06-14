"""
Simple polling service for getting updates from Telegram Bot API
Works without webhook - bot itself requests updates
"""
import asyncio
import time
import httpx
import logging
from typing import Optional, Dict, Any, List, Set
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.user_service import get_or_create_user
from app.services.telegram import telegram_service
from app.services.coingecko_quick import (
    coingecko_quick,
    _cache_get as _redis_json_get,
    _cache_set as _redis_json_set,
)
from app.services.chart_generator import chart_generator
from app.services.chart_storage import chart_storage
from app.utils.formatters import format_price


# Strong refs to fire-and-forget inline tasks so they are not GC'd mid-flight
_background_tasks: Set["asyncio.Task"] = set()

# --- Inline query tuning ---
# Timeframes shown in the results list (first one is highlighted by Telegram).
_INLINE_TIMEFRAMES = ((7, "7D"), (1, "1D"), (30, "30D"))
# Reuse window: identical (coin, timeframe) within this many seconds shares the
# same rendered image, URL and results payload.
_INLINE_BUCKET_SECONDS = 60
# symbol -> in-flight build task (single-flight dedup)
_inline_inflight: Dict[str, "asyncio.Task"] = {}


def _inline_bucket() -> int:
    return int(time.time() // _INLINE_BUCKET_SECONDS)


class MessageHandler:
    """Handles Telegram message updates"""

    @staticmethod
    async def process(message: Dict[str, Any], db: SessionLocal, logger):
        """Process a message update"""
        try:
            # Check if there's a sender
            if "from" not in message:
                return

            from_user = message["from"]
            user_id = from_user.get("id")

            if not user_id:
                return

            # Get chat info
            chat = message.get("chat", {})
            chat_id = chat.get("id")

            if not chat_id:
                return

            # Get message text
            text = message.get("text", "").strip()

            # Process /start command
            if text == "/start" or text.startswith("/start"):
                # Create or update user
                user = get_or_create_user(
                    db=db,
                    user_id=user_id,
                    username=from_user.get("username"),
                    first_name=from_user.get("first_name"),
                    last_name=from_user.get("last_name"),
                    language_code=from_user.get("language_code"),
                )

                # Send welcome message
                welcome_message = (
                    "👋 Welcome to CryptoWatcher!\n\n"
                    "🔔 Create notifications for cryptocurrency price changes\n"
                    "📊 Track charts and get alerts\n\n"
                    "Open the app to get started!"
                )

                await telegram_service.send_message(
                    chat_id=user_id,
                    text=welcome_message,
                )
                return

        except Exception as e:
            logger.exception("Error processing message")


class InlineQueryHandler:
    """Handles Telegram inline query updates.

    Hot-path design (fast -> slow):
      1. answerInlineQuery cache_time       - Telegram caches the same query string
      2. Redis results payload (per bucket) - cross-query / cross-user reuse
      3. in-process single-flight           - dedups concurrent identical builds
      4. deterministic image cache          - reuse rendered JPEG for (coin,days,bucket)
      5. Redis CoinGecko data cache         - avoid hitting the API rate limit
    """

    @staticmethod
    async def _render_one(
        coin_data: Dict[str, Any],
        coin_id: str,
        days: int,
        label: str,
        chart_data: List[Dict[str, Any]],
        preloaded_icon,
        bucket: int,
    ) -> Optional[Dict[str, Any]]:
        """Build one InlineQueryResultPhoto, reusing a cached image when one
        already exists for this (coin, timeframe, time-bucket)."""
        try:
            price_text = format_price(coin_data["price"])
            change = coin_data["percent_change_24h"]
            change_text = f"{change:+.2f}%"
            change_emoji = "📈" if change >= 0 else "📉"

            # Deterministic, URL-safe id; stable for the whole bucket window
            safe_coin = str(coin_id).replace("/", "_")
            chart_id = f"{safe_coin}_{days}_{bucket}"

            if not chart_storage.has_fresh(chart_id):
                if not chart_data:
                    return None
                chart_bytes = await chart_generator.generate_chart(
                    coin_symbol=coin_data["symbol"],
                    coin_name=coin_data["name"],
                    current_price=coin_data["price"],
                    percent_change_24h=change,
                    chart_data=chart_data,
                    days=days,
                    market_cap=coin_data.get("market_cap"),
                    volume_24h=coin_data.get("volume_24h"),
                    high_24h=coin_data.get("high_24h"),
                    low_24h=coin_data.get("low_24h"),
                    preloaded_icon=preloaded_icon,
                )
                if not chart_bytes:
                    return None
                chart_storage.store_chart_with_id(chart_id, chart_bytes, coin_data["symbol"])

            allowed_origins = settings.ALLOWED_ORIGINS.split(",")
            base_url = allowed_origins[0].strip().rstrip("/")
            image_url = f"{base_url}/api/v1/charts/{chart_id}"

            caption = (
                f"📊 <b>{coin_data['name']} ({coin_data['symbol']})</b> • {label}\n"
                f"💰 {price_text}\n"
                f"{change_emoji} {change_text}"
            )

            return {
                "type": "photo",
                "id": f"{coin_data['symbol']}_{days}d",
                "photo_url": image_url,
                "thumbnail_url": image_url,
                "photo_width": chart_generator.WIDTH_PX,
                "photo_height": chart_generator.HEIGHT_PX,
                "title": f"{coin_data['name']} ({coin_data['symbol']}) • {label}",
                "description": f"{price_text} {change_emoji} {change_text}",
                "caption": caption,
                "parse_mode": "HTML",
            }
        except Exception:
            logging.getLogger(__name__).exception("Error generating chart result")
            return None

    @staticmethod
    async def _build_results(symbol: str) -> List[Dict[str, Any]]:
        """The expensive path: fetch coin + chart data (cached) and render the
        per-timeframe photo results."""
        coin_data = await coingecko_quick.search_coin_with_price(symbol)
        if not coin_data:
            return []

        coin_id = coin_data.get("id")
        coin_icon_url = coin_data.get("large") or coin_data.get("thumb")
        bucket = _inline_bucket()

        # Icon + all chart datasets in ONE parallel batch (each Redis-cached)
        gathered = await asyncio.gather(
            chart_generator._load_icon(coin_icon_url, size=256),
            *[coingecko_quick.get_coin_chart_data(coin_id, days=d)
              for d, _ in _INLINE_TIMEFRAMES],
            return_exceptions=True,
        )
        preloaded_icon = None if isinstance(gathered[0], Exception) else gathered[0]
        chart_by_days: Dict[int, Any] = {}
        for (d, _), cd in zip(_INLINE_TIMEFRAMES, gathered[1:]):
            chart_by_days[d] = None if isinstance(cd, Exception) else cd

        rendered = await asyncio.gather(*[
            InlineQueryHandler._render_one(
                coin_data, coin_id, d, label,
                chart_by_days.get(d) or [], preloaded_icon, bucket)
            for d, label in _INLINE_TIMEFRAMES
        ], return_exceptions=True)

        results = [r for r in rendered if r and not isinstance(r, Exception)]

        # Fallback: plain article if every render failed (e.g. no chart data)
        if not results:
            price_text = format_price(coin_data["price"])
            change = coin_data["percent_change_24h"]
            emoji = "📈" if change >= 0 else "📉"
            results = [{
                "type": "article",
                "id": f"coin_{coin_data['symbol']}",
                "title": f"{coin_data['name']} ({coin_data['symbol']})",
                "description": f"{price_text} {emoji} {change:+.2f}%",
                "input_message_content": {
                    "message_text": (
                        f"📊 {coin_data['name']} ({coin_data['symbol']})\n"
                        f"💰 {price_text}\n{emoji} {change:+.2f}%"
                    ),
                },
            }]
        return results

    @staticmethod
    async def _get_results(symbol: str) -> List[Dict[str, Any]]:
        """Results with Redis payload cache + single-flight in front of the build."""
        bucket = _inline_bucket()
        cache_key = f"inline:res:{symbol}:{bucket}"

        cached = await _redis_json_get(cache_key)
        if cached is not None:
            return cached

        # Single-flight: concurrent queries for the same symbol share one build
        existing = _inline_inflight.get(symbol)
        if existing is not None:
            return await existing

        task = asyncio.ensure_future(InlineQueryHandler._build_results(symbol))
        _inline_inflight[symbol] = task
        try:
            results = await task
        finally:
            _inline_inflight.pop(symbol, None)

        await _redis_json_set(cache_key, results, _INLINE_BUCKET_SECONDS)
        return results

    @staticmethod
    async def process(inline_query: Dict[str, Any], logger):
        """Process an inline query update"""
        try:
            query_id = inline_query.get("id")
            query_text = inline_query.get("query", "").strip().upper()

            if not query_id:
                return

            if not query_text:
                await telegram_service.answer_inline_query(query_id, [])
                return

            if len(query_text) > 10:
                query_text = query_text[:10]

            results = await InlineQueryHandler._get_results(query_text)

            logger.debug(f"Sending {len(results)} inline query results for {query_text}")
            success = await telegram_service.answer_inline_query(
                query_id, results, cache_time=_INLINE_BUCKET_SECONDS
            )
            if not success:
                logger.warning(f"Failed to answer inline query for {query_text}")

        except Exception:
            logger.exception("Error processing inline query")


class UpdateDispatcher:
    """Dispatches updates to appropriate handlers"""

    @staticmethod
    async def process(update: Dict[str, Any], db: SessionLocal, logger):
        """Process a single update"""
        try:
            update_id = update.get("update_id")
            logger.debug(f"Processing update {update_id}, keys: {list(update.keys())}")

            # Handle inline query — run as a background task so heavy chart
            # rendering never blocks the poll loop from fetching new updates.
            if "inline_query" in update:
                logger.info(f"Received inline query: {update['inline_query'].get('query', '')}")
                task = asyncio.create_task(
                    InlineQueryHandler.process(update["inline_query"], logger)
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
                return

            # Handle chosen inline result
            if "chosen_inline_result" in update:
                logger.info(f"Received chosen inline result: {update['chosen_inline_result'].get('result_id', '')}")
                # Photo is sent natively by Telegram from the inline result
                return

            # Handle message
            if "message" in update:
                await MessageHandler.process(update["message"], db, logger)
                return

        except Exception as e:
            logger.exception("Error processing update")


class BotPolling:

    BASE_URL = settings.TELEGRAM_API_URL

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.offset = 0
        self.running = False
        self._logger = logging.getLogger(__name__)

        # Create single HTTP client (reused across all polls)
        _proxy = settings.TELEGRAM_PROXY or None
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            **({'proxies': _proxy} if _proxy else {}),
        )

        if not self.bot_token:
            self._logger.warning("TELEGRAM_BOT_TOKEN is not set")

    def _get_url(self, method: str) -> str:
        return f"{self.BASE_URL}{self.bot_token}/{method}"

    async def _poll_updates(self):
        if not self.bot_token:
            await asyncio.sleep(10)
            return

        try:
            params = {
                "offset": self.offset,
                "timeout": 10,
                "allowed_updates": ["message", "inline_query", "chosen_inline_result"],
            }

            response = await self.http_client.get(
                self._get_url("getUpdates"),
                params=params,
            )

            if response.status_code != 200:
                await asyncio.sleep(5)
                return

            result = response.json()

            if not result.get("ok"):
                error_description = result.get("description", "Unknown error")
                self._logger.error(f"Error from Telegram API: {error_description}")
                await asyncio.sleep(5)
                return

            updates = result.get("result", [])

            if updates:
                self._logger.debug(f"Received {len(updates)} updates")
                # Create DB session for processing updates
                db = SessionLocal()
                try:
                    for update in updates:
                        # Update offset before processing
                        self.offset = update["update_id"] + 1
                        await UpdateDispatcher.process(update, db, self._logger)
                finally:
                    db.close()

        except httpx.TimeoutException:
            pass
        except Exception as e:
            self._logger.exception("Error polling updates")
            await asyncio.sleep(5)

    async def start(self):
        if not self.bot_token:
            return

        self.running = True
        self._logger.info("Telegram bot polling started")

        while self.running:
            try:
                await self._poll_updates()
            except Exception as e:
                self._logger.error(f"Critical error: {str(e)}")
                await asyncio.sleep(5)

    async def stop(self):
        """Stop polling and close HTTP client"""
        self.running = False
        await self.http_client.aclose()
        self._logger.info("Polling stopped")


# Global instance
bot_polling = BotPolling()
