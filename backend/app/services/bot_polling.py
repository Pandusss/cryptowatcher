"""
Simple polling service for getting updates from Telegram Bot API
Works without webhook - bot itself requests updates
"""
import asyncio
import httpx
import logging
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.user_service import get_or_create_user
from app.services.telegram import telegram_service
from app.services.coingecko_quick import coingecko_quick
from app.services.chart_generator import chart_generator
from app.services.chart_storage import chart_storage
from app.utils.formatters import get_price_decimals
from app.utils.formatters import get_price_decimals


class BotPolling:
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.offset = 0
        self.running = False
        self._logger = logging.getLogger("BotPolling")

        
        if not self.bot_token:
            self._logger.warning("TELEGRAM_BOT_TOKEN is not set")
    
    def _get_url(self, method: str) -> str:
        return f"{self.BASE_URL}{self.bot_token}/{method}"
    
    async def _process_message(self, message: Dict[str, Any], db: SessionLocal):
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
                
                success = await telegram_service.send_message(
                    chat_id=user_id,
                    text=welcome_message,
                )
                return
        
        except Exception as e:
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def _process_inline_query(self, inline_query: Dict[str, Any]):
        """Process an inline query update"""
        try:
            query_id = inline_query.get("id")
            query_text = inline_query.get("query", "").strip().upper()
            from_user = inline_query.get("from", {})
            
            if not query_id:
                return
            
            # If query is empty or too short, don't search
            if not query_text or len(query_text) < 1:
                # Return empty result
                await telegram_service.answer_inline_query(query_id, [])
                return
            
            # Limit query length
            if len(query_text) > 10:
                query_text = query_text[:10]
            
            # Search for coin
            coin_data = await coingecko_quick.get_coin_full_data(query_text, days=7)
            
            if not coin_data:
                # Return empty result if coin not found
                await telegram_service.answer_inline_query(query_id, [])
                return
            
            # Prepare price info (used in both fallback and main result)
            # Use adaptive decimal places based on price value
            price = coin_data['price']
            price_decimals = get_price_decimals(price)
            # For prices < 1000, don't use thousands separator (comma)
            if price >= 1000:
                price_text = f"${price:,.{price_decimals}f}"
            else:
                price_text = f"${price:.{price_decimals}f}"
            change_text = f"{coin_data['percent_change_24h']:+.2f}%"
            change_emoji = "📈" if coin_data['percent_change_24h'] >= 0 else "📉"
            
            # Generate chart image with icon
            coin_icon_url = coin_data.get("large") or coin_data.get("thumb")
            chart_bytes = await chart_generator.generate_chart(
                coin_symbol=coin_data["symbol"],
                coin_name=coin_data["name"],
                current_price=coin_data["price"],
                percent_change_24h=coin_data["percent_change_24h"],
                chart_data=coin_data.get("chart_data", []),
                days=7,
                coin_icon_url=coin_icon_url,
                market_cap=coin_data.get("market_cap"),
                volume_24h=coin_data.get("volume_24h"),
                high_24h=coin_data.get("high_24h"),
                low_24h=coin_data.get("low_24h"),
            )
            
            if not chart_bytes:
                # Fallback to text if chart generation fails
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
                await telegram_service.answer_inline_query(query_id, [result])
                return
            
            # Store chart and get ID
            chart_id = chart_storage.store_chart(chart_bytes, coin_data["symbol"])
            
            # Build image URL using first origin from ALLOWED_ORIGINS
            allowed_origins = settings.ALLOWED_ORIGINS.split(",")
            base_url = allowed_origins[0].strip().rstrip('/')
            image_url = f"{base_url}/api/v1/charts/{chart_id}"
            
            self._logger.info(f"Generated chart for {coin_data['symbol']}, URL: {image_url}")
            
            # Use article type with zero-width space trick for image embedding
            # Zero-width space (U+200B) between brackets allows Telegram to embed the image
            # Format: [​](image_url) where ​ is zero-width space
            zwsp = "\u200B"  # Zero-width space character
            
            # Format message with embedded image using zero-width space trick
            # The zero-width space must be BETWEEN the brackets
            message_text = (
                f"[{zwsp}]({image_url})\n\n"
                f"📊 {coin_data['name']} ({coin_data['symbol']})\n"
                f"💰 {price_text}\n"
                f"{change_emoji} {change_text}"
            )
            
            result = {
                "type": "article",
                "id": f"coin_{coin_data['symbol']}",
                "title": f"{coin_data['name']} ({coin_data['symbol']})",
                "description": f"{price_text} {change_emoji} {change_text}",
                "input_message_content": {
                    "message_text": message_text,
                    "parse_mode": "Markdown",
                },
                "thumb_url": image_url,  # Thumbnail for preview
            }
            
            self._logger.debug(f"Sending inline query result for {coin_data['symbol']}")
            success = await telegram_service.answer_inline_query(query_id, [result])
            if not success:
                self._logger.warning(f"Failed to answer inline query for {coin_data['symbol']}")
            
        except Exception as e:
            self._logger.error(f"Error processing inline query: {e}", exc_info=True)
    
    async def _process_chosen_inline_result(self, chosen_result: Dict[str, Any]):
        """Process chosen inline result - chart is already embedded via zero-width space"""
        # Chart is already sent via inline message with embedded image
        # No need to send separate photo
        pass
    
    async def _process_update(self, update: Dict[str, Any], db: SessionLocal):
        """Process a single update"""
        try:
            update_id = update.get("update_id")
            self._logger.debug(f"Processing update {update_id}, keys: {list(update.keys())}")
            
            # Handle inline query
            if "inline_query" in update:
                self._logger.info(f"Received inline query: {update['inline_query'].get('query', '')}")
                await self._process_inline_query(update["inline_query"])
                return
            
            # Handle chosen inline result
            if "chosen_inline_result" in update:
                self._logger.info(f"Received chosen inline result: {update['chosen_inline_result'].get('result_id', '')}")
                await self._process_chosen_inline_result(update["chosen_inline_result"])
                return
            
            # Handle message
            if "message" in update:
                await self._process_message(update["message"], db)
                return
        
        except Exception as e:
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def _poll_updates(self):
        if not self.bot_token:
            await asyncio.sleep(10)
            return
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # httpx should serialize array correctly for Telegram API
                params = {
                    "offset": self.offset,
                    "timeout": 10,
                    "allowed_updates": ["message", "inline_query", "chosen_inline_result"],
                }
                
                response = await client.get(
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
                            await self._process_update(update, db)
                    finally:
                        db.close()
        
        except httpx.TimeoutException:
            pass
        except Exception as e:
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
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
    
    def stop(self):
        self.running = False
        self._logger.info("Polling stopped")

# Global instance
bot_polling = BotPolling()