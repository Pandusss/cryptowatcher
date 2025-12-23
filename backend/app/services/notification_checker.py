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
        self.check_interval = 300
        self.price_cache_ttl = 10
        self._logger = logging.getLogger("NotificationChecker")
    
    def _check_notification_condition(
        self,
        notification: Notification,
        current_price: float,
    ) -> bool:
        original_price = notification.current_price
        price_change = current_price - original_price
        
        if notification.value_type == NotificationValueType.PRICE:
            if notification.direction == NotificationDirection.RISE:
                return current_price >= notification.value
            elif notification.direction == NotificationDirection.FALL:
                return current_price <= notification.value
            else:
                return abs(current_price - notification.value) < 0.01
        elif notification.direction == NotificationDirection.RISE:
            if notification.value_type == NotificationValueType.PERCENT:
                change_percent = (price_change / original_price) * 100
                return change_percent >= notification.value
            else:
                return price_change >= notification.value
        elif notification.direction == NotificationDirection.FALL:
            if notification.value_type == NotificationValueType.PERCENT:
                change_percent = abs((price_change / original_price) * 100)
                return change_percent >= notification.value and price_change < 0
            else:
                return abs(price_change) >= notification.value and price_change < 0
        else:
            if notification.value_type == NotificationValueType.PERCENT:
                change_percent = abs((price_change / original_price) * 100)
                return change_percent >= notification.value
            else:
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
            if self._check_notification_condition(notification, current_price):
                db.refresh(notification)
                
                if not notification.is_active:
                    return False
                
                user = db.query(User).filter(User.id == notification.user_id).first()
                if user and self._is_dnd_active(user):
                    return False
                
                updated = db.query(Notification).filter(
                    Notification.id == notification.id,
                    Notification.is_active == True
                ).update({
                    'is_active': False,
                    'triggered_at': datetime.utcnow()
                }, synchronize_session=False)
                
                if updated == 0:
                    return False
                
                db.commit()
                
                success = await telegram_service.send_notification(
                    user_id=notification.user_id,
                    crypto_id=notification.crypto_id,
                    crypto_name=notification.crypto_name,
                    crypto_symbol=notification.crypto_symbol,
                    current_price=current_price,
                    direction=notification.direction.value,
                    trigger=notification.trigger.value,
                    value=notification.value,
                    value_type=notification.value_type.value,
                )
                
                if success:
                    return True
                else:
                    return False
            
            return False
        
        except Exception as e:
            import traceback
            self._logger.error(f"Error processing notification {notification.id}: {str(e)}")
            self._logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _is_dnd_active(self, user: User) -> bool:
        if not user.dnd_start_time or not user.dnd_end_time:
            return False
        
        current_time = datetime.utcnow().time()
        start_time = user.dnd_start_time
        end_time = user.dnd_end_time
        
        if start_time < end_time:
            return start_time <= current_time <= end_time
        
        return current_time >= start_time or current_time <= end_time
    
    def _check_notification_expired(self, notification: Notification) -> bool:
        if notification.expire_time_hours is None:
            return False
        
        expire_time = notification.created_at + timedelta(hours=notification.expire_time_hours)
        current_time = datetime.now(expire_time.tzinfo)
        
        return current_time >= expire_time
    
    async def check_notifications_for_coin(self, coin_id: str):
        """
        Event-driven notification check for a specific coin.
        Called when price is updated via WebSocket.
        Reads price from Redis and checks all active notifications for this coin.
        
        Args:
            coin_id: Internal coin ID
        """
        db = SessionLocal()
        try:
            # Get active notifications for this coin only
            active_notifications = db.query(Notification).filter(
                Notification.crypto_id == coin_id,
                Notification.is_active == True
            ).all()
            
            if not active_notifications:
                return
            
            valid_notifications = []
            expired_count = 0
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
            
            current_price = await self._get_crypto_price(coin_id)
            
            if current_price is None:
                return
            
            for notification in valid_notifications:
                await self._check_and_process_notification(notification, current_price, db)
        
        except Exception as e:
            import traceback
            self._logger.error(f"Error checking notifications for coin {coin_id}: {str(e)}")
            self._logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            db.close()
    
    async def check_all_notifications(self):
        """
        Periodic fallback check for all active notifications.
        Runs every check_interval seconds to catch any missed updates.
        """
        db = SessionLocal()
        try:
            # Get all active notifications
            active_notifications = db.query(Notification).filter(
                Notification.is_active == True
            ).all()
            
            if not active_notifications:
                return
            
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
            
            notifications_by_crypto: Dict[str, List[Notification]] = defaultdict(list)
            for notification in valid_notifications:
                notifications_by_crypto[notification.crypto_id].append(notification)
            
            for crypto_id, notifications in notifications_by_crypto.items():
                current_price = await self._get_crypto_price(crypto_id)
                
                if current_price is None:
                    continue
                
                for notification in notifications:
                    await self._check_and_process_notification(notification, current_price, db)
                
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
            
            await asyncio.sleep(self.check_interval)
    
    def stop(self):
        self.running = False
        self._logger.warning(f"Notification checking stopped")    


# Global instance
notification_checker = NotificationChecker()