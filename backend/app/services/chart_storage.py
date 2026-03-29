"""
Chart image storage service
Stores generated chart images temporarily for inline queries
"""
import logging
from collections import OrderedDict
from typing import Optional, Dict
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class ChartStorage:
    """Temporary storage for chart images with size limit and auto-cleanup"""

    def __init__(self, ttl_hours: int = 24, max_items: int = 500):
        self.storage: OrderedDict[str, Dict] = OrderedDict()
        self.ttl_hours = ttl_hours
        self.max_items = max_items

    def store_chart(self, image_bytes: bytes, symbol: str) -> str:
        import secrets

        self.cleanup_expired()

        # Evict oldest entries if at capacity
        while len(self.storage) >= self.max_items:
            evicted_id, _ = self.storage.popitem(last=False)
            logger.debug(f"Evicted oldest chart {evicted_id} (capacity limit)")

        chart_id = secrets.token_urlsafe(16)
        now = datetime.now(timezone.utc)

        self.storage[chart_id] = {
            "image_bytes": image_bytes,
            "symbol": symbol,
            "created_at": now,
            "expires_at": now + timedelta(hours=self.ttl_hours),
        }

        logger.debug(f"Stored chart for {symbol} with ID {chart_id}")
        return chart_id

    def get_chart(self, chart_id: str) -> Optional[bytes]:
        if chart_id not in self.storage:
            return None

        chart_data = self.storage[chart_id]

        if datetime.now(timezone.utc) > chart_data["expires_at"]:
            del self.storage[chart_id]
            logger.debug(f"Chart {chart_id} expired, removed")
            return None

        return chart_data["image_bytes"]

    def cleanup_expired(self):
        """Remove expired charts"""
        now = datetime.now(timezone.utc)
        expired_ids = [
            chart_id for chart_id, data in self.storage.items()
            if now > data["expires_at"]
        ]

        for chart_id in expired_ids:
            del self.storage[chart_id]

        if expired_ids:
            logger.debug(f"Cleaned up {len(expired_ids)} expired charts")

    def get_stats(self) -> Dict:
        """Get storage statistics"""
        self.cleanup_expired()
        return {
            "total_charts": len(self.storage),
            "max_items": self.max_items,
            "ttl_hours": self.ttl_hours,
        }


# Global instance
chart_storage = ChartStorage(ttl_hours=24, max_items=500)
