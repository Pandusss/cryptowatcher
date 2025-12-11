"""
Конфигурация приложения из переменных окружения (.env файл)

Все переменные обязательны и должны быть указаны в .env файле.
Pydantic автоматически валидирует типы и выдает ошибку при старте, если что-то не так.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = Field(default="CryptoWatcher") 
    APP_VERSION: str = Field(default="0.1.0")
    DEBUG: bool = Field(...) 

    # Database
    DATABASE_URL: str = Field(...)

    # Redis
    REDIS_URL: str = Field(...)

    # CoinGecko API 
    COINGECKO_API_KEY: str = Field(default="")

    # Telegram Bot API
    TELEGRAM_BOT_TOKEN: str = Field(...)

    # CORS - храним как строку, парсим в main.py
    ALLOWED_ORIGINS: str = Field(...)

    model_config = SettingsConfigDict(
        env_file="../.env", 
        case_sensitive=True,
        extra="ignore", 
    )


settings = Settings()

