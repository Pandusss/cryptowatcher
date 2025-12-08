"""
Endpoints для обработки команд Telegram бота (webhook)
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.database import get_db
from app.services.user_service import get_or_create_user
from app.services.telegram import telegram_service

router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Webhook endpoint для получения обновлений от Telegram Bot API
    
    Telegram отправляет обновления в формате:
    {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": false,
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
                "language_code": "en"
            },
            "chat": {...},
            "date": 1234567890,
            "text": "/start"
        }
    }
    """
    try:
        # Логируем входящий запрос
        body = await request.body()
        print(f"[Bot Webhook] Получен запрос: {body.decode('utf-8')[:500]}")
        
        update: Dict[str, Any] = await request.json()
        print(f"[Bot Webhook] Parsed update: {update}")
        
        # Проверяем, что это сообщение
        if "message" not in update:
            print("[Bot Webhook] Нет поля 'message' в update")
            return {"ok": True}
        
        message = update["message"]
        
        # Проверяем, что есть отправитель
        if "from" not in message:
            print("[Bot Webhook] Нет поля 'from' в message")
            return {"ok": True}
        
        from_user = message["from"]
        user_id = from_user.get("id")
        
        if not user_id:
            print("[Bot Webhook] Нет user_id в from")
            return {"ok": True}
        
        # Получаем текст сообщения
        text = message.get("text", "").strip()
        print(f"[Bot Webhook] Сообщение от пользователя {user_id}: '{text}'")
        
        # Обрабатываем команду /start
        if text == "/start" or text.startswith("/start"):
            print(f"[Bot Webhook] Обработка команды /start от пользователя {user_id}")
            
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
                print(f"[Bot Webhook] ✅ Команда /start обработана успешно для пользователя {user_id}")
            else:
                print(f"[Bot Webhook] ❌ Ошибка отправки сообщения пользователю {user_id}")
        else:
            print(f"[Bot Webhook] Неизвестная команда: '{text}'")
        
        return {"ok": True}
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[Bot Webhook] ❌ Ошибка при обработке webhook: {str(e)}")
        print(f"[Bot Webhook] Traceback: {error_trace}")
        # Возвращаем ok, чтобы Telegram не повторял запрос
        return {"ok": True}


@router.get("/set-webhook")
async def set_webhook(webhook_url: str):
    """
    Установить webhook URL для Telegram бота
    
    Использование:
    GET /api/v1/bot/set-webhook?webhook_url=https://yourdomain.com/api/v1/bot/webhook
    """
    try:
        import httpx
        
        bot_token = telegram_service.bot_token
        if not bot_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN не установлен")
        
        print(f"[Bot] Установка webhook: {webhook_url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{bot_token}/setWebhook",
                json={"url": webhook_url},
            )
            result = response.json()
            
            print(f"[Bot] Ответ от Telegram API: {result}")
            
            if result.get("ok"):
                return {
                    "status": "success",
                    "message": "Webhook установлен",
                    "url": webhook_url,
                    "telegram_response": result
                }
            else:
                error_description = result.get("description", "Unknown error")
                raise HTTPException(
                    status_code=400,
                    detail=f"Ошибка установки webhook: {error_description}"
                )
    except Exception as e:
        import traceback
        print(f"[Bot] Ошибка установки webhook: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/get-webhook-info")
async def get_webhook_info():
    """
    Получить информацию о текущем webhook
    
    Использование:
    GET /api/v1/bot/get-webhook-info
    """
    try:
        import httpx
        
        bot_token = telegram_service.bot_token
        if not bot_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN не установлен")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getWebhookInfo",
            )
            result = response.json()
            
            return {
                "status": "success",
                "webhook_info": result
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/delete-webhook")
async def delete_webhook():
    """
    Удалить webhook
    
    Использование:
    GET /api/v1/bot/delete-webhook
    """
    try:
        import httpx
        
        bot_token = telegram_service.bot_token
        if not bot_token:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN не установлен")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{bot_token}/deleteWebhook",
            )
            result = response.json()
            
            return {
                "status": "success",
                "message": "Webhook удален",
                "telegram_response": result
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

