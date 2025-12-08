from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "CryptoWatcher"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/cryptowatcher"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CoinGecko API (опционально, для увеличения лимитов)
    COINGECKO_API_KEY: str = ""

    # Telegram Bot API
    TELEGRAM_BOT_TOKEN: str = ""  # Токен бота от @BotFather

    # CORS - храним как строку, парсим в main.py
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file="../.env",  # Читаем общий .env из корня проекта
        case_sensitive=True,
        extra="ignore",  # Игнорируем лишние поля из .env
    )

    def get_allowed_origins_list(self) -> List[str]:
        """Парсит ALLOWED_ORIGINS из строки в список"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()

