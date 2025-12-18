from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router
from app.services.bot_polling import bot_polling
from app.services.notification_checker import notification_checker
from app.providers.binance_websocket import binance_websocket_worker
from app.providers.okx_websocket import okx_websocket_worker
from app.providers.mexc_websocket import mexc_websocket_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Manages startup and shutdown of background services.
    """
    import asyncio
    
    # Startup: Start all background services
    asyncio.create_task(bot_polling.start())
    asyncio.create_task(notification_checker.start())
    asyncio.create_task(binance_websocket_worker.start())
    asyncio.create_task(okx_websocket_worker.start())
    asyncio.create_task(mexc_websocket_worker.start())
    
    yield
    
    # Shutdown: Stop all services and cleanup
    bot_polling.stop()
    notification_checker.stop()
    binance_websocket_worker.stop()
    okx_websocket_worker.stop()
    mexc_websocket_worker.stop()
    
    # Close WebSocket connections
    await binance_websocket_worker.close()
    await okx_websocket_worker.close()
    await mexc_websocket_worker.close()
    
    # Close shared HTTP client
    from app.utils.http_client import SharedHTTPClient
    await SharedHTTPClient.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
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
