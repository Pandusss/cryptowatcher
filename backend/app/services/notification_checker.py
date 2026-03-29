"""
Service for checking notification conditions and sending alerts
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from collections import defaultdict

from app.core.database import async_db_session
from app.core.redis_client import get_redis
from app.models.notification import Notification, NotificationDirection, NotificationTrigger, NotificationValueType
from app.models.user import User
from app.services.aggregation_service import aggregation_service
from app.services.telegram import telegram_service

logger = logging.getLogger(__name__)


class NotificationChecker:

    def __init__(self):
        self.aggregation_service = aggregation_service
        self.running = False
        self.check_interval = 300
        self.price_cache_ttl = 10
        self._coin_locks: Dict[str, asyncio.Lock] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}

    def _get_coin_lock(self, coin_id: str) -> asyncio.Lock:
        if coin_id not in self._coin_locks:
            self._coin_locks[coin_id] = asyncio.Lock()
        return self._coin_locks[coin_id]

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
            return None
        except Exception as e:
            logger.warning(f"Failed to get price for {crypto_id}: {e}")
            return None

    async def _run_sync(self, func):
        """Run a synchronous function in executor to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func)

    async def _check_and_process_notification(
        self,
        notification: Notification,
        current_price: float,
        db: Session,
    ) -> bool:
        try:
            if self._check_notification_condition(notification, current_price):
                await self._run_sync(lambda: db.refresh(notification))

                if not notification.is_active:
                    return False

                user = await self._run_sync(
                    lambda: db.query(User).filter(User.id == notification.user_id).first()
                )
                if user and self._is_dnd_active(user):
                    return False

                updated = await self._run_sync(lambda: db.query(Notification).filter(
                    Notification.id == notification.id,
                    Notification.is_active == True
                ).update({
                    'is_active': False,
                    'triggered_at': datetime.now(timezone.utc)
                }, synchronize_session=False))

                if updated == 0:
                    return False

                await self._run_sync(db.commit)

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

                return success

            return False

        except Exception as e:
            logger.exception(f"Error processing notification {notification.id}")
            return False

    def _is_dnd_active(self, user: User) -> bool:
        if not user.dnd_start_time or not user.dnd_end_time:
            return False

        current_time = datetime.now(timezone.utc).time()
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
        Uses per-coin lock to prevent parallel checks for the same coin.
        """
        lock = self._get_coin_lock(coin_id)
        if lock.locked():
            return

        async with lock:
            await self._check_notifications_for_coin_inner(coin_id)

    async def _check_notifications_for_coin_inner(self, coin_id: str):
        async with async_db_session() as db:
            try:
                active_notifications = await self._run_sync(
                    lambda: db.query(Notification).filter(
                        Notification.crypto_id == coin_id,
                        Notification.is_active == True
                    ).all()
                )

                if not active_notifications:
                    return

                valid_notifications = []
                expired_count = 0
                for notification in active_notifications:
                    if self._check_notification_expired(notification):
                        await self._run_sync(lambda n=notification: db.delete(n))
                        expired_count += 1
                    else:
                        valid_notifications.append(notification)

                if expired_count > 0:
                    await self._run_sync(db.commit)

                if not valid_notifications:
                    return

                current_price = await self._get_crypto_price(coin_id)

                if current_price is None:
                    return

                for notification in valid_notifications:
                    await self._check_and_process_notification(notification, current_price, db)

            except Exception as e:
                logger.exception(f"Error checking notifications for coin {coin_id}")

    async def check_all_notifications(self):
        """
        Periodic fallback check for all active notifications.
        Runs every check_interval seconds to catch any missed updates.
        """
        async with async_db_session() as db:
            try:
                active_notifications = await self._run_sync(
                    lambda: db.query(Notification).filter(
                        Notification.is_active == True
                    ).all()
                )

                if not active_notifications:
                    return

                expired_count = 0
                valid_notifications = []
                for notification in active_notifications:
                    if self._check_notification_expired(notification):
                        await self._run_sync(lambda n=notification: db.delete(n))
                        expired_count += 1
                    else:
                        valid_notifications.append(notification)

                if expired_count > 0:
                    await self._run_sync(db.commit)

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

            except Exception as e:
                logger.exception("Error in check_all_notifications")

    async def start(self):
        self.running = True

        while self.running:
            try:
                await self.check_all_notifications()
            except Exception as e:
                logger.exception("Critical error in notification checker")

            await asyncio.sleep(self.check_interval)

    def stop(self):
        self.running = False
        logger.info("Notification checking stopped")


# Global instance
notification_checker = NotificationChecker()
