"""
Service for sending notifications to Telegram via Bot API
"""
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
                except:
                    error_message += f": {e.response.text[:200]}"
            else:
                error_message += f": {e.response.text[:200]}"
            
            logger.error(error_message)
            return False
    
    async def send_notification(
        self,
        user_id: int,
        crypto_name: str,
        crypto_symbol: str,
        current_price: float,
        direction: str,
        trigger: str,
        value: float,
        value_type: str,
    ) -> bool:

        # Format price
        def format_price(price: float) -> str:
            if price >= 1000000:
                return f"${(price / 1000000):.2f}M"
            elif price >= 1000:
                return f"${(price / 1000):.2f}K"
            else:
                return f"${price:.2f}"
        
        # Determine direction for text
        direction_text = {
            "rise": "выросла",
            "fall": "упала",
            "both": "изменилась",
        }.get(direction, "изменилась")
        
        # Determine trigger type for text
        trigger_text = {
            "stop-loss": "Stop-loss",
            "take-profit": "Take-profit",
        }.get(trigger, "Alert")
        
        # Format value
        if value_type == "percent":
            value_text = f"{value}%"
        else:
            value_text = format_price(value)
        
        # Form message
        message = (
            f"🔔 <b>{trigger_text}</b>\n\n"
            f"<b>{crypto_name} ({crypto_symbol})</b> {direction_text} by {value_text}\n\n"
            f"Current price: <b>{format_price(current_price)}</b>"
        )
        
        return await self.send_message(user_id, message)


# Create global service instance
telegram_service = TelegramService()

