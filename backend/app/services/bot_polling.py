"""
Simple polling service for getting updates from Telegram Bot API
Works without webhook - bot itself requests updates
"""
import asyncio
import httpx
import logging
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.user_service import get_or_create_user
from app.services.telegram import telegram_service
from app.services.coingecko_quick import coingecko_quick
from app.services.chart_generator import chart_generator
from app.services.chart_storage import chart_storage
from app.utils.formatters import get_price_decimals


def format_price(price: float) -> str:
    """Format price with proper decimals and thousands separator"""
    decimals = get_price_decimals(price)
    if price >= 1000:
        return f"${price:,.{decimals}f}"
    return f"${price:.{decimals}f}"


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
    """Handles Telegram inline query updates"""
    
    @staticmethod
    async def _generate_chart_result(
        coin_data: Dict[str, Any],
        days: int,
        timeframe_label: str,
        chart_data: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate a single chart result for inline query"""
        try:
            # Use provided chart_data or fetch it
            if chart_data is None:
                coin_id = coin_data.get("id")
                if not coin_id:
                    return None
                chart_data = await coingecko_quick.get_coin_chart_data(coin_id, days=days)
            
            if not chart_data:
                return None
            
            # Prepare price info
            price_text = format_price(coin_data['price'])
            change_text = f"{coin_data['percent_change_24h']:+.2f}%"
            change_emoji = "📈" if coin_data['percent_change_24h'] >= 0 else "📉"
            
            # Generate chart image
            coin_icon_url = coin_data.get("large") or coin_data.get("thumb")
            chart_bytes = await chart_generator.generate_chart(
                coin_symbol=coin_data["symbol"],
                coin_name=coin_data["name"],
                current_price=coin_data["price"],
                percent_change_24h=coin_data["percent_change_24h"],
                chart_data=chart_data,
                days=days,
                coin_icon_url=coin_icon_url,
                market_cap=coin_data.get("market_cap"),
                volume_24h=coin_data.get("volume_24h"),
                high_24h=coin_data.get("high_24h"),
                low_24h=coin_data.get("low_24h"),
            )
            
            if not chart_bytes:
                return None
            
            # Store chart and get ID
            chart_id = chart_storage.store_chart(chart_bytes, coin_data["symbol"])
            
            # Build image URL
            allowed_origins = settings.ALLOWED_ORIGINS.split(",")
            base_url = allowed_origins[0].strip().rstrip('/')
            image_url = f"{base_url}/api/v1/charts/{chart_id}"
            
            # Format message with embedded image
            zwsp = "\u200B"  # Zero-width space
            message_text = (
                f"[{zwsp}]({image_url})\n\n"
                f"📊 {coin_data['name']} ({coin_data['symbol']}) • {timeframe_label}\n"
                f"💰 {price_text}\n"
                f"{change_emoji} {change_text}"
            )
            
            return {
                "type": "article",
                "id": f"coin_{coin_data['symbol']}_{days}d",
                "title": f"{coin_data['name']} ({coin_data['symbol']}) • {timeframe_label}",
                "description": f"{price_text} {change_emoji} {change_text}",
                "input_message_content": {
                    "message_text": message_text,
                    "parse_mode": "Markdown",
                },
                "thumb_url": image_url,
            }
        except Exception as e:
            logging.getLogger("InlineQueryHandler").exception(f"Error generating chart result")
            return None
    
    @staticmethod
    async def process(inline_query: Dict[str, Any], logger):
        """Process an inline query update"""
        try:
            query_id = inline_query.get("id")
            query_text = inline_query.get("query", "").strip().upper()
            
            if not query_id:
                return
            
            # If query is empty or too short, don't search
            if not query_text or len(query_text) < 1:
                await telegram_service.answer_inline_query(query_id, [])
                return
            
            # Limit query length
            if len(query_text) > 10:
                query_text = query_text[:10]
            
            # Search for coin (use default 7D for initial search)
            coin_data = await coingecko_quick.get_coin_full_data(query_text, days=7)
            
            if not coin_data:
                await telegram_service.answer_inline_query(query_id, [])
                return
            
            # Prepare price info for fallback
            price_text = format_price(coin_data['price'])
            change_text = f"{coin_data['percent_change_24h']:+.2f}%"
            change_emoji = "📈" if coin_data['percent_change_24h'] >= 0 else "📉"
            
            # Generate results for different timeframes in parallel for better performance
            # Reuse already fetched 7D chart_data to avoid redundant API call
            chart_data_7d = coin_data.get("chart_data", [])
            coin_id = coin_data.get("id")
            
            result_7d, result_1d, result_30d = await asyncio.gather(
                InlineQueryHandler._generate_chart_result(coin_data, days=7, timeframe_label="7D", chart_data=chart_data_7d),
                InlineQueryHandler._generate_chart_result(coin_data, days=1, timeframe_label="1D", chart_data=None),
                InlineQueryHandler._generate_chart_result(coin_data, days=30, timeframe_label="30D", chart_data=None),
                return_exceptions=True
            )
            
            results = []
            if result_7d and not isinstance(result_7d, Exception):
                results.append(result_7d)
            if result_1d and not isinstance(result_1d, Exception):
                results.append(result_1d)
            if result_30d and not isinstance(result_30d, Exception):
                results.append(result_30d)
            
            # If no chart results, fallback to text
            if not results:
                result = {
                    "type": "article",
                    "id": f"coin_{coin_data['symbol']}",
                    "title": f"{coin_data['name']} ({coin_data['symbol']})",
                    "description": f"{price_text} {change_emoji} {change_text}",
                    "input_message_content": {
                        "message_text": f"📊 {coin_data['name']} ({coin_data['symbol']})\n"
                                       f"💰 {price_text}\n"
                                       f"{change_emoji} {change_text}",
                    },
                }
                results = [result]
            
            logger.debug(f"Sending {len(results)} inline query results for {coin_data['symbol']}")
            success = await telegram_service.answer_inline_query(query_id, results)
            if not success:
                logger.warning(f"Failed to answer inline query for {coin_data['symbol']}")
            
        except Exception as e:
            logger.exception("Error processing inline query")


class UpdateDispatcher:
    """Dispatches updates to appropriate handlers"""
    
    @staticmethod
    async def process(update: Dict[str, Any], db: SessionLocal, logger):
        """Process a single update"""
        try:
            update_id = update.get("update_id")
            logger.debug(f"Processing update {update_id}, keys: {list(update.keys())}")
            
            # Handle inline query
            if "inline_query" in update:
                logger.info(f"Received inline query: {update['inline_query'].get('query', '')}")
                await InlineQueryHandler.process(update["inline_query"], logger)
                return
            
            # Handle chosen inline result
            if "chosen_inline_result" in update:
                logger.info(f"Received chosen inline result: {update['chosen_inline_result'].get('result_id', '')}")
                # Chart is already sent via inline message with embedded image
                # No need to send separate photo
                return
            
            # Handle message
            if "message" in update:
                await MessageHandler.process(update["message"], db, logger)
                return
        
        except Exception as e:
            logger.exception("Error processing update")


class BotPolling:
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.offset = 0
        self.running = False
        self._logger = logging.getLogger("BotPolling")
        
        # Create single HTTP client (reused across all polls)
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
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