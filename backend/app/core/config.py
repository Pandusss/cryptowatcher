"""
Application configuration from environment variables (.env file)

Most variables are required and must be specified in the .env file.
Pydantic automatically validates types and shows error at startup if something is wrong.

DEBUG is False by default (for production security).
"""
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env path relative to project root (two levels up from this file)
_ENV_FILE = str(Path(__file__).resolve().parents[3] / ".env")


class Settings(BaseSettings):
    # Application
    APP_NAME: str = Field(default="CryptoWatcher")
    APP_VERSION: str = Field(default="0.1.0")
    DEBUG: bool = Field(default=False)

    # Database
    DATABASE_URL: str = Field(...)
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)

    # Redis
    REDIS_URL: str = Field(...)

    # CoinGecko API
    COINGECKO_API_KEY: str = Field(default="")
    COINGECKO_UPDATE_INTERVAL: int = Field(default=15)

    # Telegram Bot API
    TELEGRAM_BOT_TOKEN: str = Field(...)
    TELEGRAM_API_URL: str = Field(default="https://api.telegram.org/bot")
    TELEGRAM_PROXY: str = Field(default="")  # socks5://user:pass@host:port

    # CORS origins (comma-separated). First origin is used for generating absolute URLs
    ALLOWED_ORIGINS: str = Field(...)

    # Cache TTLs (seconds)
    CACHE_TTL_STATIC: int = Field(default=3600)
    CACHE_TTL_PRICE: int = Field(default=86400)
    CACHE_TTL_CHART: int = Field(default=60)
    CACHE_TTL_IMAGE: int = Field(default=604800)

    # WebSocket
    WS_RECONNECT_DELAY: int = Field(default=1)
    WS_MAX_RECONNECT_DELAY: int = Field(default=120)

    # Chart storage
    CHART_STORAGE_MAX_ITEMS: int = Field(default=500)
    CHART_STORAGE_TTL_HOURS: int = Field(default=24)

    # HTTP client
    HTTP_MAX_CONNECTIONS: int = Field(default=10)
    HTTP_MAX_KEEPALIVE: int = Field(default=5)

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        case_sensitive=True,
        extra="ignore",
    )

settings = Settings()
