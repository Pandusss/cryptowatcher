"""
Service for checking notification conditions and sending alerts
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from collections import defaultdict

from app.core.database import SessionLocal
from app.core.redis_client import get_redis
from app.models.notification import Notification, NotificationDirection, NotificationTrigger, NotificationValueType
from app.models.user import User
from app.services.aggregation_service import aggregation_service
from app.services.telegram import telegram_service


class NotificationChecker:
    
    def __init__(self):
        self.aggregation_service = aggregation_service
        self.running = False
        self.check_interval = 60  # Check every 60 seconds
        self.price_cache_ttl = 10  # Cache prices for 10 seconds for relevance
        self._logger = logging.getLogger("NotificationChecker")
    
    def _check_notification_condition(
        self,
        notification: Notification,
        current_price: float,
    ) -> bool:
        original_price = notification.current_price
        price_change = current_price - original_price
        
        # Check condition based on direction
        if notification.value_type == NotificationValueType.PRICE:
            # If type is "price", compare current price with specified price
            if notification.direction == NotificationDirection.RISE:
                # Price should rise to specified price or above
                return current_price >= notification.value
            elif notification.direction == NotificationDirection.FALL:
                # Price should fall to specified price or below
                return current_price <= notification.value
            else:  # BOTH
                # Price should reach specified price (any direction)
                return abs(current_price - notification.value) < 0.01  # Small tolerance for float comparison
        elif notification.direction == NotificationDirection.RISE:
            # Price should rise
            if notification.value_type == NotificationValueType.PERCENT:
                change_percent = (price_change / original_price) * 100
                return change_percent >= notification.value
            else:  # ABSOLUTE
                return price_change >= notification.value
        
        elif notification.direction == NotificationDirection.FALL:
            # Price should fall
            if notification.value_type == NotificationValueType.PERCENT:
                change_percent = abs((price_change / original_price) * 100)
                return change_percent >= notification.value and price_change < 0
            else:  # ABSOLUTE
                return abs(price_change) >= notification.value and price_change < 0
        
        else:  # BOTH
            # Check change in any direction
            if notification.value_type == NotificationValueType.PERCENT:
                change_percent = abs((price_change / original_price) * 100)
                return change_percent >= notification.value
            else:  # ABSOLUTE
                return abs(price_change) >= notification.value
    
    async def _get_crypto_price(self, crypto_id: str) -> Optional[float]:
        try:
            price_data = await self.aggregation_service.get_coin_price(crypto_id)
            if price_data:
                price = price_data.get("price", 0)
                if price > 0:
                    return price
                else:
                    return None
            else:
                return None
        except Exception as e:
            return None
    
    async def _check_and_process_notification(
        self,
        notification: Notification,
        current_price: float,
        db: Session,
    ) -> bool:
        try:
            # Check condition
            if self._check_notification_condition(notification, current_price):
                
                # Check user DND mode
                user = db.query(User).filter(User.id == notification.user_id).first()
                if user and self._is_dnd_active(user):
                    # Don't send notification but also don't deactivate it - it will trigger later
                    return False
                
                # Send notification to Telegram
                success = await telegram_service.send_notification(
                    user_id=notification.user_id,
                    crypto_name=notification.crypto_name,
                    crypto_symbol=notification.crypto_symbol,
                    current_price=current_price,
                    direction=notification.direction.value,
                    trigger=notification.trigger.value,
                    value=notification.value,
                    value_type=notification.value_type.value,
                )
                
                # Mark notification as triggered and deactivate in any case
                # (to avoid spamming if user hasn't started the bot or blocked it)
                notification.triggered_at = datetime.utcnow()
                notification.is_active = False  # Deactivate after triggering
                db.commit()
                
                if success:
                    return True
                else:
                    return False
            
            return False
        
        except Exception as e:
            import traceback
            return False
    
    def _is_dnd_active(self, user: User) -> bool:
        if not user.dnd_start_time or not user.dnd_end_time:
            # If DND is not set up, notifications are always sent
            return False
        
        # Get current UTC time
        current_time = datetime.utcnow().time()
        start_time = user.dnd_start_time
        end_time = user.dnd_end_time
        
        # If start_time < end_time, then DND is within one day
        # For example: 12:00 - 19:00 means DND from 12:00 to 19:00
        if start_time < end_time:
            return start_time <= current_time <= end_time
        
        # If start_time >= end_time, then DND crosses midnight
        # For example: 22:00 - 08:00 means DND from 22:00 to 08:00 next day
        # In this case DND is active if current_time >= start_time OR current_time <= end_time
        return current_time >= start_time or current_time <= end_time
    
    def _check_notification_expired(self, notification: Notification) -> bool:
        if notification.expire_time_hours is None:
            # Permanent notification
            return False
        
        # Calculate expiration time
        expire_time = notification.created_at + timedelta(hours=notification.expire_time_hours)
        current_time = datetime.now(expire_time.tzinfo)
        
        return current_time >= expire_time
    
    async def check_all_notifications(self):
        db = SessionLocal()
        try:
            # Get all active notifications
            active_notifications = db.query(Notification).filter(
                Notification.is_active == True
            ).all()
            
            if not active_notifications:
                return
                        
            # First check and delete expired notifications
            expired_count = 0
            valid_notifications = []
            for notification in active_notifications:
                if self._check_notification_expired(notification):
                    db.delete(notification)
                    expired_count += 1
                else:
                    valid_notifications.append(notification)
            
            if expired_count > 0:
                db.commit()
            
            if not valid_notifications:
                return
            
            # Group notifications by crypto_id
            notifications_by_crypto: Dict[str, List[Notification]] = defaultdict(list)
            for notification in valid_notifications:
                notifications_by_crypto[notification.crypto_id].append(notification)
                        
            # Check each cryptocurrency once
            for crypto_id, notifications in notifications_by_crypto.items():
                # Get current price (with caching)
                current_price = await self._get_crypto_price(crypto_id)
                
                if current_price is None:
                    continue
                
                # Check all notifications for this cryptocurrency
                for notification in notifications:
                    await self._check_and_process_notification(notification, current_price, db)
                
                # Small delay between cryptocurrencies
                await asyncio.sleep(0.5)
        
        finally:
            db.close()
    
    async def start(self):
        self.running = True
        
        while self.running:
            try:
                await self.check_all_notifications()
            except Exception as e:
                import traceback
                self._logger.error(f"Critical error: {str(e)}")
                self._logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Wait before next check
            await asyncio.sleep(self.check_interval)
    
    def stop(self):
        self.running = False
        self._logger.warning(f"Notification checking stopped")    


# Global instance
notification_checker = NotificationChecker()