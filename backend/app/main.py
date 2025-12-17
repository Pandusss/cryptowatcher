from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.core.config import settings
from app.api.v1.router import api_router
from app.services.bot_polling import bot_polling
from app.services.notification_checker import notification_checker
from app.providers.binance_websocket import binance_websocket_worker
from app.providers.okx_websocket import okx_websocket_worker

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# CORS middleware
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
    # Start polling for bot command processing
    asyncio.create_task(bot_polling.start())
    
    # Start notification checking
    asyncio.create_task(notification_checker.start())
    
    # Start Binance WebSocket
    asyncio.create_task(binance_websocket_worker.start())
    
    # Start OKX WebSocket
    asyncio.create_task(okx_websocket_worker.start())


@app.on_event("shutdown")
async def shutdown_event():
    bot_polling.stop()
    notification_checker.stop()
    binance_websocket_worker.stop()  # Stop Binance WebSocket
    okx_websocket_worker.stop()  # Stop OKX WebSocket
    
    # Close WebSocket connections to prevent memory leaks
    await binance_websocket_worker.close()
    await okx_websocket_worker.close()
    
    # Close shared HTTP client
    from app.utils.http_client import SharedHTTPClient
    await SharedHTTPClient.close()