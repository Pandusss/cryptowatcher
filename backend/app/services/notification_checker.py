"""
Сервис для проверки условий уведомлений и отправки алертов
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
        self.check_interval = 60  # Проверяем каждые 60 секунд
        self.price_cache_ttl = 10  # Кэшируем цены на 10 секунд для актуальности
        self._logger = logging.getLogger("NotificationChecker")
    
    def _check_notification_condition(
        self,
        notification: Notification,
        current_price: float,
    ) -> bool:

        original_price = notification.current_price
        price_change = current_price - original_price
        
        # Проверяем условие в зависимости от направления
        if notification.value_type == NotificationValueType.PRICE:
            # Если тип "price", сравниваем текущую цену с указанной ценой
            if notification.direction == NotificationDirection.RISE:
                # Цена должна подняться до указанной цены или выше
                return current_price >= notification.value
            elif notification.direction == NotificationDirection.FALL:
                # Цена должна упасть до указанной цены или ниже
                return current_price <= notification.value
            else:  # BOTH
                # Цена должна достичь указанной цены (в любом направлении)
                return abs(current_price - notification.value) < 0.01  # Небольшая погрешность для сравнения float
        elif notification.direction == NotificationDirection.RISE:
            # Цена должна подняться
            if notification.value_type == NotificationValueType.PERCENT:
                change_percent = (price_change / original_price) * 100
                return change_percent >= notification.value
            else:  # ABSOLUTE
                return price_change >= notification.value
        
        elif notification.direction == NotificationDirection.FALL:
            # Цена должна упасть
            if notification.value_type == NotificationValueType.PERCENT:
                change_percent = abs((price_change / original_price) * 100)
                return change_percent >= notification.value and price_change < 0
            else:  # ABSOLUTE
                return abs(price_change) >= notification.value and price_change < 0
        
        else:  # BOTH
            # Проверяем изменение в любом направлении
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
            # Проверяем условие
            if self._check_notification_condition(notification, current_price):
                
                # Проверяем DND режим пользователя
                user = db.query(User).filter(User.id == notification.user_id).first()
                if user and self._is_dnd_active(user):
                    # Не отправляем уведомление, но и не деактивируем его - оно сработает позже
                    return False
                
                # Отправляем уведомление в Telegram
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
                
                # Помечаем уведомление как сработавшее и деактивируем в любом случае
                # (чтобы не спамить, если пользователь не запустил бота или заблокировал его)
                notification.triggered_at = datetime.utcnow()
                notification.is_active = False  # Деактивируем после срабатывания
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
            # Если DND не настроен, уведомления отправляются всегда
            return False
        
        # Получаем текущее время UTC
        current_time = datetime.utcnow().time()
        start_time = user.dnd_start_time
        end_time = user.dnd_end_time
        
        # Если start_time < end_time, то DND в пределах одного дня
        # Например: 12:00 - 19:00 означает DND с 12:00 до 19:00
        if start_time < end_time:
            return start_time <= current_time <= end_time
        
        # Если start_time >= end_time, то DND переходит через полночь
        # Например: 22:00 - 08:00 означает DND с 22:00 до 08:00 следующего дня
        # В этом случае DND активен если current_time >= start_time ИЛИ current_time <= end_time
        return current_time >= start_time or current_time <= end_time
    
    def _check_notification_expired(self, notification: Notification) -> bool:

        if notification.expire_time_hours is None:
            # Бессрочное уведомление
            return False
        
        # Вычисляем время истечения
        expire_time = notification.created_at + timedelta(hours=notification.expire_time_hours)
        current_time = datetime.now(expire_time.tzinfo)
        
        return current_time >= expire_time
    
    async def check_all_notifications(self):

        db = SessionLocal()
        try:
            # Получаем все активные уведомления
            active_notifications = db.query(Notification).filter(
                Notification.is_active == True
            ).all()
            
            if not active_notifications:
                return
                        
            # Сначала проверяем и удаляем истекшие уведомления
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
            
            # Группируем уведомления по crypto_id
            notifications_by_crypto: Dict[str, List[Notification]] = defaultdict(list)
            for notification in valid_notifications:
                notifications_by_crypto[notification.crypto_id].append(notification)
                        
            # Проверяем каждую криптовалюту один раз
            for crypto_id, notifications in notifications_by_crypto.items():
                # Получаем текущую цену (с кэшированием)
                current_price = await self._get_crypto_price(crypto_id)
                
                if current_price is None:
                    continue
                
                # Проверяем все уведомления для этой криптовалюты
                for notification in notifications:
                    await self._check_and_process_notification(notification, current_price, db)
                
                # Небольшая задержка между криптовалютами
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
            
            # Ждем перед следующей проверкой
            await asyncio.sleep(self.check_interval)
    
    def stop(self):

        self.running = False
        self._logger.warning(f"Notification verification stopped")    


# Глобальный экземпляр
notification_checker = NotificationChecker()

