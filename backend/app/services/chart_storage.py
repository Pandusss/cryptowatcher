"""
Chart image storage service
Stores generated chart images temporarily for inline queries
"""
import logging
import secrets
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger("ChartStorage")


class ChartStorage:
    """Temporary storage for chart images"""
    
    def __init__(self, ttl_hours: int = 24):
        """
        Initialize storage
        
        Args:
            ttl_hours: Time to live for stored images in hours
        """
        self.storage: Dict[str, Dict] = {}
        self.ttl_hours = ttl_hours
        self._logger = logging.getLogger("ChartStorage")
    
    def store_chart(self, image_bytes: bytes, symbol: str) -> str:
        """
        Store chart image and return unique ID
        
        Args:
            image_bytes: PNG image bytes
            symbol: Coin symbol for reference
            
        Returns:
            Unique chart ID
        """
        # Generate unique ID
        chart_id = secrets.token_urlsafe(16)
        
        # Store with metadata
        self.storage[chart_id] = {
            "image_bytes": image_bytes,
            "symbol": symbol,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=self.ttl_hours),
        }
        
        self._logger.debug(f"Stored chart for {symbol} with ID {chart_id}")
        return chart_id
    
    def get_chart(self, chart_id: str) -> Optional[bytes]:
        """
        Get chart image by ID
        
        Args:
            chart_id: Chart ID
            
        Returns:
            Image bytes or None if not found/expired
        """
        if chart_id not in self.storage:
            return None
        
        chart_data = self.storage[chart_id]
        
        # Check if expired
        if datetime.utcnow() > chart_data["expires_at"]:
            del self.storage[chart_id]
            self._logger.debug(f"Chart {chart_id} expired, removed")
            return None
        
        return chart_data["image_bytes"]
    
    def cleanup_expired(self):
        """Remove expired charts"""
        now = datetime.utcnow()
        expired_ids = [
            chart_id for chart_id, data in self.storage.items()
            if now > data["expires_at"]
        ]
        
        for chart_id in expired_ids:
            del self.storage[chart_id]
        
        if expired_ids:
            self._logger.debug(f"Cleaned up {len(expired_ids)} expired charts")
    
    def get_stats(self) -> Dict:
        """Get storage statistics"""
        self.cleanup_expired()
        return {
            "total_charts": len(self.storage),
            "ttl_hours": self.ttl_hours,
        }


# Global instance
chart_storage = ChartStorage(ttl_hours=24)

