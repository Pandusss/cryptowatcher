from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.core.config import settings
from app.api.v1.router import api_router
from app.services.bot_polling import bot_polling
from app.services.notification_checker import notification_checker
from app.services.coins_cache_updater import coins_cache_updater
from app.services.prices_updater import prices_updater

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins_list(),
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
    
    # Запускаем фоновое обновление цен каждые 10 секунд
    asyncio.create_task(prices_updater.start())
    
    # Отключено: больше не нужна фоновая задача для топ-3000, используем batch API для монет из конфига
    # asyncio.create_task(coins_cache_updater.start())


@app.on_event("shutdown")
async def shutdown_event():
    """Остановка фоновых задач при выключении приложения"""
    bot_polling.stop()
    notification_checker.stop()
    prices_updater.stop()
    # coins_cache_updater.stop()  # Отключено

