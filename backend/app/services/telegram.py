"""
Service for sending notifications to Telegram via Bot API
"""
import asyncio
import httpx
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(f"TelegramService")

class TelegramService:
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        if not self.bot_token:
            logger.error(f"TELEGRAM_BOT_TOKEN is not installed. Notifications will not be sent")
    
    def _get_url(self, method: str) -> str:
        return f"{self.BASE_URL}{self.bot_token}/{method}"
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = "HTML",
        disable_web_page_preview: bool = True,
    ) -> bool:

        if not self.bot_token:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self._get_url("sendMessage"),
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": disable_web_page_preview,
                    },
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("ok"):
                    return True
                else:
                    error_description = result.get("description", "Unknown error")
                    logger.error(f"Error sending the message: {error_description}")
                    return False
                    
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_message = f"HTTP error {status_code}"
            
            if status_code == 400:
                try:
                    error_data = e.response.json()
                    error_code = error_data.get("error_code")
                    description = error_data.get("description", "")
                    if error_code and description:
                        error_message += f" (Telegram API {error_code}: {description})"
                    else:
                        error_message += f": {e.response.text[:200]}"
                except Exception:
                    error_message += f": {e.response.text[:200]}"
            else:
                error_message += f": {e.response.text[:200]}"
            
            logger.error(error_message)
            return False
    
    async def send_notification(
        self,
        user_id: int,
        crypto_id: str,
        crypto_name: str,
        crypto_symbol: str,
        current_price: float,
        direction: str,
        trigger: str,
        value: float,
        value_type: str,
    ) -> bool:
        from app.utils.formatters import get_price_decimals
        from app.services.chart_generator import chart_generator
        from app.services.chart_storage import chart_storage
        from app.services.coingecko_quick import coingecko_quick
        from app.core.config import settings

        # Format price with proper decimals (full amount, no abbreviations)
        def format_price(price: float) -> str:
            decimals = get_price_decimals(price)
            return f"${price:.{decimals}f}"
        
        # Determine direction for text with emoji
        direction_info = {
            "rise": ("increased", "↑"),
            "fall": ("decreased", "↓"),
            "both": ("changed", "↔"),
        }.get(direction, ("changed", "↔"))
        direction_text, direction_emoji = direction_info
        
        # Determine trigger type for text with emoji
        trigger_info = {
            "stop-loss": ("Stop-loss", "🔴"),
            "take-profit": ("Take-profit", "🟢"),
        }.get(trigger, ("Alert", "🔔"))
        trigger_text, trigger_emoji = trigger_info
        
        # Format value and message based on value type
        if value_type == "price":
            # For price type: "reached $X" or "increased/decreased to $X"
            value_text = format_price(value)
            if direction == "rise":
                change_text = f"increased to <b>{value_text}</b>"
            elif direction == "fall":
                change_text = f"decreased to <b>{value_text}</b>"
            else:
                change_text = f"reached <b>{value_text}</b>"
        elif value_type == "percent":
            # For percent type: "increased/decreased by X%"
            value_text = f"{value:+.2f}%"
            change_text = f"{direction_text} by <b>{value_text}</b> {direction_emoji}"
        else:
            # For absolute type: "increased/decreased by $X"
            value_text = format_price(value)
            change_text = f"{direction_text} by <b>{value_text}</b> {direction_emoji}"
        
        # Form message with improved formatting
        message = (
            f"{trigger_emoji} <b>{trigger_text}</b>\n"
            f"<b>{crypto_name} ({crypto_symbol})</b> {change_text}\n"
            f"Current price: <b>{format_price(current_price)}</b>"
        )
        
        # Try to generate and send chart image
        try:
            logger.info(f"Generating chart for notification: {crypto_symbol} ({crypto_name})")
            
            # Get full coin data from CoinGecko (same as inline commands)
            coin_data = await coingecko_quick.get_coin_full_data(crypto_symbol, days=7)
            
            if not coin_data:
                logger.warning(f"No coin data received for {crypto_symbol}")
            elif not coin_data.get("chart_data"):
                logger.warning(f"No chart data for {crypto_symbol}")
            else:
                # Get chart data (already in correct format: [{"timestamp": int, "price": float}])
                chart_data = coin_data.get("chart_data", [])
                logger.info(f"Got {len(chart_data)} chart data points for {crypto_symbol}")
                
                if chart_data:
                    # Get all data from coin_data
                    coin_icon_url = coin_data.get("large") or coin_data.get("thumb")
                    
                    # Determine base image type
                    base_image_type = None
                    if trigger == "take-profit":
                        base_image_type = "take-profit"
                    elif trigger == "stop-loss":
                        base_image_type = "stop-loss"
                    
                    # Generate chart image with all data from CoinGecko
                    chart_bytes = await chart_generator.generate_chart(
                        coin_symbol=crypto_symbol,
                        coin_name=crypto_name,
                        current_price=current_price,  # Use current_price from notification (most accurate)
                        percent_change_24h=coin_data.get("percent_change_24h", 0),
                        chart_data=chart_data,
                        days=7,
                        coin_icon_url=coin_icon_url,
                        market_cap=coin_data.get("market_cap"),
                        volume_24h=coin_data.get("volume_24h"),
                        high_24h=coin_data.get("high_24h"),
                        low_24h=coin_data.get("low_24h"),
                        base_image_type=base_image_type,
                    )
                    
                    if chart_bytes:
                        logger.info(f"Chart generated successfully for {crypto_symbol}, size: {len(chart_bytes)} bytes")
                        
                        # Send photo with caption (more reliable than Markdown trick for regular messages)
                        return await self.send_photo(
                            user_id,
                            chart_bytes,
                            caption=message,
                            parse_mode="HTML"
                        )
                    else:
                        logger.warning(f"Chart generation returned None for {crypto_symbol}")
        
        except Exception as e:
            logger.error(f"Error generating chart for notification: {e}", exc_info=True)
            # Fall back to text message if chart generation fails
        
        # Fall back to text message if chart generation failed
        return await self.send_message(user_id, message)
    
    async def send_photo(
        self,
        chat_id: int,
        photo_bytes: bytes,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = "HTML",
    ) -> bool:
        """
        Send photo to chat
        
        Args:
            chat_id: Chat ID
            photo_bytes: Photo image bytes
            caption: Optional caption text
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bot_token:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {
                    "photo": ("chart.png", photo_bytes, "image/png")
                }
                data = {
                    "chat_id": chat_id,
                }
                if caption:
                    data["caption"] = caption
                if parse_mode:
                    data["parse_mode"] = parse_mode
                
                response = await client.post(
                    self._get_url("sendPhoto"),
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("ok"):
                    return True
                else:
                    error_description = result.get("description", "Unknown error")
                    logger.error(f"Error sending photo: {error_description}")
                    return False
                    
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_message = f"HTTP error {status_code}"
            
            if status_code == 400:
                try:
                    error_data = e.response.json()
                    error_code = error_data.get("error_code")
                    description = error_data.get("description", "")
                    if error_code and description:
                        error_message += f" (Telegram API {error_code}: {description})"
                    else:
                        error_message += f": {e.response.text[:200]}"
                except Exception:
                    error_message += f": {e.response.text[:200]}"
            else:
                error_message += f": {e.response.text[:200]}"
            
            logger.error(error_message)
            return False
    
    async def answer_inline_query(
        self,
        inline_query_id: str,
        results: list,
        cache_time: int = 300,
    ) -> bool:
        """
        Answer inline query
        
        Args:
            inline_query_id: Inline query ID
            results: List of InlineQueryResult objects
            cache_time: Cache time in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bot_token:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self._get_url("answerInlineQuery"),
                    json={
                        "inline_query_id": inline_query_id,
                        "results": results,
                        "cache_time": cache_time,
                    },
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("ok"):
                    return True
                else:
                    error_description = result.get("description", "Unknown error")
                    logger.error(f"Error answering inline query: {error_description}")
                    # Log the full response for debugging
                    logger.error(f"Full response: {result}")
                    return False
                    
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_message = f"HTTP error {status_code}"
            
            if status_code == 400:
                try:
                    error_data = e.response.json()
                    error_code = error_data.get("error_code")
                    description = error_data.get("description", "")
                    if error_code and description:
                        error_message += f" (Telegram API {error_code}: {description})"
                    else:
                        error_message += f": {e.response.text[:200]}"
                except Exception:
                    error_message += f": {e.response.text[:200]}"
            else:
                error_message += f": {e.response.text[:200]}"
            
            logger.error(error_message)
            return False


# Create global service instance
telegram_service = TelegramService()

