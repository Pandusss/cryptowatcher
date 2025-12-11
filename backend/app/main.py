from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.core.config import settings
from app.api.v1.router import api_router
from app.services.bot_polling import bot_polling
from app.services.notification_checker import notification_checker
# Устаревшие сервисы удалены:
# - prices_updater.py - заменен на Binance WebSocket
# - coins_cache_updater.py - больше не нужен
from app.providers.binance_websocket import binance_websocket_worker
from app.providers.okx_websocket import okx_websocket_worker

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# CORS middleware
# Парсим ALLOWED_ORIGINS из строки в список (формат: "http://localhost:5173,http://localhost:3000")
allowed_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "CryptoWatcher API", "version": settings.APP_VERSION}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    """Запуск фоновых задач при старте приложения"""
    # Запускаем polling для обработки команд бота
    asyncio.create_task(bot_polling.start())
    
    # Запускаем проверку уведомлений
    asyncio.create_task(notification_checker.start())
    
    # Запускаем Binance WebSocket для real-time цен (заменяет CoinGecko polling)
    asyncio.create_task(binance_websocket_worker.start())
    
    # Запускаем OKX WebSocket как fallback для монет, которых нет на Binance
    asyncio.create_task(okx_websocket_worker.start())
    
    # Отключено: CoinGecko polling заменен на Binance WebSocket для real-time обновлений
    # asyncio.create_task(prices_updater.start())
    
    # Отключено: больше не нужна фоновая задача для топ-3000, используем batch API для монет из конфига
    # asyncio.create_task(coins_cache_updater.start())


@app.on_event("shutdown")
async def shutdown_event():
    """Остановка фоновых задач при выключении приложения"""
    bot_polling.stop()
    notification_checker.stop()
    binance_websocket_worker.stop()  # Останавливаем Binance WebSocket
    okx_websocket_worker.stop()  # Останавливаем OKX WebSocket
    # prices_updater.stop()  # Отключено (заменен на Binance WebSocket)
    # coins_cache_updater.stop()  # Отключено
    
    # Закрываем WebSocket соединения для предотвращения утечек памяти
    await binance_websocket_worker.close()
    await okx_websocket_worker.close()
    
    # Закрываем общий HTTP клиент
    from app.utils.http_client import SharedHTTPClient
    await SharedHTTPClient.close()
    # await prices_updater.close()  # Отключено

