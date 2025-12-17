"""
Простой polling сервис для получения обновлений от Telegram Bot API
Работает без webhook - бот сам запрашивает обновления
"""
import asyncio
import httpx
import logging
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.user_service import get_or_create_user
from app.services.telegram import telegram_service


class BotPolling:
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.offset = 0
        self.running = False
        self._logger = logging.getLogger("BotPolling")

        
        if not self.bot_token:
            self._logger.warning("TELEGRAM_BOT_TOKEN is not installed")
    
    def _get_url(self, method: str) -> str:
        return f"{self.BASE_URL}{self.bot_token}/{method}"
    
    async def _process_update(self, update: Dict[str, Any], db: SessionLocal):
        try:
            # Проверяем, что это сообщение
            if "message" not in update:
                return
            
            message = update["message"]
            
            # Проверяем, что есть отправитель
            if "from" not in message:
                return
            
            from_user = message["from"]
            user_id = from_user.get("id")
            
            if not user_id:
                return
            
            # Получаем текст сообщения
            text = message.get("text", "").strip()
                        
            # Обрабатываем команду /start
            if text == "/start" or text.startswith("/start"):                
                # Создаем или обновляем пользователя
                user = get_or_create_user(
                    db=db,
                    user_id=user_id,
                    username=from_user.get("username"),
                    first_name=from_user.get("first_name"),
                    last_name=from_user.get("last_name"),
                    language_code=from_user.get("language_code"),
                )
                
                # Отправляем приветственное сообщение
                welcome_message = (
                    "👋 Добро пожаловать в CryptoWatcher!\n\n"
                    "🔔 Создавайте уведомления о изменении цен криптовалют\n"
                    "📊 Отслеживайте графики и получайте алерты\n\n"
                    "Откройте приложение для начала работы!"
                )
                
                success = await telegram_service.send_message(
                    chat_id=user_id,
                    text=welcome_message,
                )
        
        except Exception as e:
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def _poll_updates(self):
        if not self.bot_token:
            await asyncio.sleep(10)
            return
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self._get_url("getUpdates"),
                    params={
                        "offset": self.offset,
                        "timeout": 10,
                        "allowed_updates": ["message"],  
                    },
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
                    # Создаем сессию БД для обработки обновлений
                    db = SessionLocal()
                    try:
                        for update in updates:
                            # Обновляем offset перед обработкой
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
        self._logger.info("Polling for Telegram bot launched")
        
        while self.running:
            try:
                await self._poll_updates()
            except Exception as e:
                self._logger.error(f"Critical error: {str(e)}")
                await asyncio.sleep(5)
    
    def stop(self):
        self.running = False
        self._logger.info("Stop polling")

# Глобальный экземпляр
bot_polling = BotPolling()

