"""
Сервис для отправки уведомлений в Telegram через Bot API
"""
import httpx
from typing import Optional
from app.core.config import settings


class TelegramService:
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        if not self.bot_token:
            print("[TelegramService] WARNING: TELEGRAM_BOT_TOKEN не установлен. Уведомления не будут отправляться.")
    
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
            print(f"[TelegramService] Пропуск отправки сообщения: токен бота не установлен")
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
                    print(f"[TelegramService] Сообщение отправлено пользователю {chat_id}")
                    return True
                else:
                    error_description = result.get("description", "Unknown error")
                    print(f"[TelegramService] Ошибка отправки сообщения: {error_description}")
                    return False
                    
        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP {e.response.status_code}: {e.response.text}"
            
            # Проверяем специфичные ошибки Telegram API
            if e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    error_code = error_data.get("error_code")
                    description = error_data.get("description", "")
                    
                    if "chat not found" in description.lower():
                        print(f"[TelegramService] ⚠️ Пользователь {chat_id} не найден (не запустил бота или заблокировал его)")
                    elif error_code == 403:
                        print(f"[TelegramService] ⚠️ Пользователь {chat_id} заблокировал бота")
                    else:
                        print(f"[TelegramService] Ошибка HTTP при отправке сообщения: {error_detail}")
                except:
                    print(f"[TelegramService] Ошибка HTTP при отправке сообщения: {error_detail}")
            else:
                print(f"[TelegramService] Ошибка HTTP при отправке сообщения: {error_detail}")
            return False
        except Exception as e:
            print(f"[TelegramService] Ошибка при отправке сообщения: {str(e)}")
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

        # Форматируем цену
        def format_price(price: float) -> str:
            if price >= 1000000:
                return f"${(price / 1000000):.2f}M"
            elif price >= 1000:
                return f"${(price / 1000):.2f}K"
            else:
                return f"${price:.2f}"
        
        # Определяем направление для текста
        direction_text = {
            "rise": "выросла",
            "fall": "упала",
            "both": "изменилась",
        }.get(direction, "изменилась")
        
        # Определяем тип триггера для текста
        trigger_text = {
            "stop-loss": "Stop-loss",
            "take-profit": "Take-profit",
        }.get(trigger, "Alert")
        
        # Форматируем значение
        if value_type == "percent":
            value_text = f"{value}%"
        else:
            value_text = format_price(value)
        
        # Формируем сообщение
        message = (
            f"🔔 <b>{trigger_text}</b>\n\n"
            f"<b>{crypto_name} ({crypto_symbol})</b> {direction_text} на {value_text}\n\n"
            f"Текущая цена: <b>{format_price(current_price)}</b>"
        )
        
        return await self.send_message(user_id, message)


# Создаем глобальный экземпляр сервиса
telegram_service = TelegramService()

