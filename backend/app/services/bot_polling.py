"""
Простой polling сервис для получения обновлений от Telegram Bot API
Работает без webhook - бот сам запрашивает обновления
"""
import asyncio
import httpx
from typing import Optional, Callable, Dict, Any
from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.services.user_service import get_or_create_user
from app.services.telegram import telegram_service


class BotPolling:
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.offset = 0
        self.running = False
        
        if not self.bot_token:
            print("[BotPolling] WARNING: TELEGRAM_BOT_TOKEN не установлен")
    
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
            
            print(f"[BotPolling] Сообщение от пользователя {user_id}: '{text}'")
            
            # Обрабатываем команду /start
            if text == "/start" or text.startswith("/start"):
                print(f"[BotPolling] Обработка команды /start от пользователя {user_id}")
                
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
                    "Откройте Mini App для начала работы!"
                )
                
                success = await telegram_service.send_message(
                    chat_id=user_id,
                    text=welcome_message,
                )
                
                if success:
                    print(f"[BotPolling] ✅ Команда /start обработана успешно для пользователя {user_id}")
                else:
                    print(f"[BotPolling] ❌ Ошибка отправки сообщения пользователю {user_id}")
        
        except Exception as e:
            import traceback
            print(f"[BotPolling] Ошибка при обработке update: {str(e)}")
            print(f"[BotPolling] Traceback: {traceback.format_exc()}")
    
    async def _poll_updates(self):
        if not self.bot_token:
            print("[BotPolling] Токен бота не установлен, пропускаем polling")
            await asyncio.sleep(10)
            return
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self._get_url("getUpdates"),
                    params={
                        "offset": self.offset,
                        "timeout": 10,  # Long polling - ждем до 10 секунд
                        "allowed_updates": ["message"],  # Только сообщения
                    },
                )
                
                if response.status_code != 200:
                    print(f"[BotPolling] Ошибка получения обновлений: {response.status_code}")
                    await asyncio.sleep(5)
                    return
                
                result = response.json()
                
                if not result.get("ok"):
                    error_description = result.get("description", "Unknown error")
                    print(f"[BotPolling] Ошибка от Telegram API: {error_description}")
                    await asyncio.sleep(5)
                    return
                
                updates = result.get("result", [])
                
                if updates:
                    print(f"[BotPolling] Получено {len(updates)} обновлений")
                    
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
            # Timeout - это нормально для long polling
            pass
        except Exception as e:
            import traceback
            print(f"[BotPolling] Ошибка при polling: {str(e)}")
            print(f"[BotPolling] Traceback: {traceback.format_exc()}")
            await asyncio.sleep(5)
    
    async def start(self):
        if not self.bot_token:
            print("[BotPolling] Токен бота не установлен, polling не запущен")
            return
        
        self.running = True
        print("[BotPolling] 🚀 Запущен polling для Telegram бота")
        
        while self.running:
            try:
                await self._poll_updates()
            except Exception as e:
                print(f"[BotPolling] Критическая ошибка: {str(e)}")
                await asyncio.sleep(5)
    
    def stop(self):
        self.running = False
        print("[BotPolling] ⏹️ Остановлен polling")


# Глобальный экземпляр
bot_polling = BotPolling()

