import logging
import logging.handlers
import os
from pathlib import Path

# Determine log directory relative to backend/
_log_dir = str(Path(__file__).resolve().parent.parent / "logs")
os.makedirs(_log_dir, exist_ok=True)

# Common format
_log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_date_format = "%Y-%m-%d %H:%M:%S"

# Stream handler (stdout)
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(logging.Formatter(_log_format, datefmt=_date_format))

# File handler with rotation (10 MB, 5 backups)
_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(_log_dir, "cryptowatcher.log"),
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(_log_format, datefmt=_date_format))

# Configure root logger (level will be adjusted after settings load if DEBUG=True)
logging.basicConfig(
    level=logging.INFO,
    handlers=[_stream_handler, _file_handler],
)

# Suppress httpx request logging (leaks bot token in URLs)
logging.getLogger("httpx").setLevel(logging.WARNING)


def configure_log_level():
    """Call after settings are loaded to set DEBUG level if needed."""
    from app.core.config import settings
    if settings.DEBUG:
        logging.getLogger().setLevel(logging.DEBUG)
