"""
Application configuration from environment variables (.env file)

Most variables are required and must be specified in the .env file.
Pydantic automatically validates types and shows error at startup if something is wrong.

DEBUG is False by default (for production security).
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = Field(default="CryptoWatcher") 
    APP_VERSION: str = Field(default="0.1.0")
    DEBUG: bool = Field(default=False)  # False by default for production 

    # Database
    DATABASE_URL: str = Field(...)

    # Redis
    REDIS_URL: str = Field(...)

    # CoinGecko API 
    COINGECKO_API_KEY: str = Field(default="")

    # Telegram Bot API
    TELEGRAM_BOT_TOKEN: str = Field(...)

    # CORS - store as string, parse in main.py
    ALLOWED_ORIGINS: str = Field(...)

    model_config = SettingsConfigDict(
        env_file="../.env", 
        case_sensitive=True,
        extra="ignore", 
    )

settings = Settings()