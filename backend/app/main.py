import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app import configure_log_level
from app.api.v1.router import api_router

configure_log_level()
from app.services.bot_polling import bot_polling
from app.services.notification_checker import notification_checker
from app.services.chart_generator import chart_generator
from app.services.chart_storage import chart_storage
from app.providers.cex.binance_websocket import binance_websocket_worker
from app.providers.cex.okx_websocket import okx_websocket_worker
from app.providers.cex.mexc_websocket import mexc_websocket_worker
from app.providers.dex.coingecko_price_updater import coingecko_price_updater
from app.services.telegram import telegram_service

logger = logging.getLogger(__name__)


def create_supervised_task(coro_func, name: str, restart_on_failure: bool = True) -> asyncio.Task:
    """Create a task that logs errors and optionally restarts on failure."""

    async def _wrapper():
        while True:
            try:
                await coro_func()
                break  # Normal exit
            except asyncio.CancelledError:
                logger.info(f"Task '{name}' cancelled")
                raise
            except Exception:
                logger.exception(f"Task '{name}' crashed")
                if not restart_on_failure:
                    break
                await asyncio.sleep(5)
                logger.info(f"Restarting task '{name}'...")

    return asyncio.create_task(_wrapper(), name=name)


async def _periodic_chart_cleanup():
    """Periodically clean up expired charts from in-memory storage."""
    while True:
        await asyncio.sleep(1800)  # Every 30 minutes
        chart_storage.cleanup_expired()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Manages startup and shutdown of background services.
    """
    # Startup: Start all background services with supervision
    tasks = [
        create_supervised_task(bot_polling.start, "bot_polling"),
        create_supervised_task(notification_checker.start, "notification_checker"),
        create_supervised_task(binance_websocket_worker.start, "binance_websocket"),
        create_supervised_task(okx_websocket_worker.start, "okx_websocket"),
        create_supervised_task(mexc_websocket_worker.start, "mexc_websocket"),
        create_supervised_task(coingecko_price_updater.start, "coingecko_updater"),
        create_supervised_task(_periodic_chart_cleanup, "chart_cleanup", restart_on_failure=False),
    ]

    yield

    # Shutdown: Cancel all supervised tasks
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)

    # Stop services gracefully
    await bot_polling.stop()
    notification_checker.stop()
    await binance_websocket_worker.close()
    await okx_websocket_worker.close()
    await mexc_websocket_worker.close()
    await coingecko_price_updater.stop()
    await coingecko_price_updater.close()

    # Close shared HTTP client
    from app.utils.http_client import SharedHTTPClient
    await SharedHTTPClient.close()

    # Close Telegram service HTTP client
    await telegram_service.close()

    # Close chart generator (HTTP client and thread pool)
    await chart_generator.close()


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
