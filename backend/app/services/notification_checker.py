"""
Сервис для проверки условий уведомлений и отправки алертов
"""
import asyncio
import json
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
    """Сервис для проверки и обработки уведомлений"""
    
    def __init__(self):
        self.aggregation_service = aggregation_service
        self.running = False
        self.check_interval = 60  # Проверяем каждые 60 секунд
        self.price_cache_ttl = 10  # Кэшируем цены на 10 секунд для актуальности
    
    def _check_notification_condition(
        self,
        notification: Notification,
        current_price: float,
    ) -> bool:
        """
        Проверить, сработало ли условие уведомления
        
        Args:
            notification: Уведомление для проверки
            current_price: Текущая цена криптовалюты
        
        Returns:
            True если условие сработало, False иначе
        """
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
        """
        Получить текущую цену криптовалюты через AggregationService
        
        Args:
            crypto_id: Внутренний ID криптовалюты
        
        Returns:
            Текущая цена или None если не удалось получить
        """
        try:
            price_data = await self.aggregation_service.get_coin_price(crypto_id)
            if price_data:
                price = price_data.get("price", 0)
                if price > 0:
                    print(f"[NotificationChecker] ✅ Цена {crypto_id} через AggregationService: ${price}")
                    return price
                else:
                    print(f"[NotificationChecker] ⚠️ Цена {crypto_id} равна 0")
                    return None
            else:
                print(f"[NotificationChecker] ⚠️ Цена {crypto_id} не найдена")
                return None
        except Exception as e:
            print(f"[NotificationChecker] Ошибка получения цены через AggregationService: {e}")
            return None
    
    async def _check_and_process_notification(
        self,
        notification: Notification,
        current_price: float,
        db: Session,
    ) -> bool:
        """
        Проверить одно уведомление и отправить алерт при срабатывании
        
        Args:
            notification: Уведомление для проверки
            current_price: Текущая цена криптовалюты (уже получена)
            db: Сессия базы данных
        
        Returns:
            True если уведомление было отправлено
        """
        try:
            # Проверяем условие
            if self._check_notification_condition(notification, current_price):
                print(f"[NotificationChecker] ✅ Уведомление {notification.id} сработало! Цена: {current_price}")
                
                # Проверяем DND режим пользователя
                user = db.query(User).filter(User.id == notification.user_id).first()
                if user and self._is_dnd_active(user):
                    print(f"[NotificationChecker] ⏸️ Уведомление {notification.id} пропущено из-за DND режима (пользователь {notification.user_id})")
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
                    print(f"[NotificationChecker] Уведомление {notification.id} отправлено и деактивировано")
                    return True
                else:
                    print(f"[NotificationChecker] ⚠️ Уведомление {notification.id} деактивировано, но отправка не удалась (возможно, пользователь не запустил бота)")
                    return False
            
            return False
        
        except Exception as e:
            import traceback
            print(f"[NotificationChecker] Ошибка при проверке уведомления {notification.id}: {str(e)}")
            print(f"[NotificationChecker] Traceback: {traceback.format_exc()}")
            return False
    
    def _is_dnd_active(self, user: User) -> bool:
        """
        Проверить, активен ли режим Don't Disturb для пользователя
        
        Args:
            user: Пользователь для проверки
        
        Returns:
            True если DND активен (уведомления не должны отправляться), False иначе
        """
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
        """
        Проверить, истекло ли время уведомления
        Возвращает True если уведомление истекло и должно быть удалено
        """
        if notification.expire_time_hours is None:
            # Бессрочное уведомление
            return False
        
        # Вычисляем время истечения
        expire_time = notification.created_at + timedelta(hours=notification.expire_time_hours)
        current_time = datetime.now(expire_time.tzinfo)
        
        return current_time >= expire_time
    
    async def check_all_notifications(self):
        """
        Проверить все активные уведомления
        
        Оптимизация: группируем уведомления по crypto_id и проверяем цену один раз для каждой криптовалюты
        """
        db = SessionLocal()
        try:
            # Получаем все активные уведомления
            active_notifications = db.query(Notification).filter(
                Notification.is_active == True
            ).all()
            
            if not active_notifications:
                return
            
            print(f"[NotificationChecker] Проверяю {len(active_notifications)} активных уведомлений")
            
            # Сначала проверяем и удаляем истекшие уведомления
            expired_count = 0
            valid_notifications = []
            for notification in active_notifications:
                if self._check_notification_expired(notification):
                    print(f"[NotificationChecker] Уведомление {notification.id} истекло (создано: {notification.created_at}, срок: {notification.expire_time_hours} часов)")
                    db.delete(notification)
                    expired_count += 1
                else:
                    valid_notifications.append(notification)
            
            if expired_count > 0:
                db.commit()
                print(f"[NotificationChecker] Удалено {expired_count} истекших уведомлений")
            
            if not valid_notifications:
                print("[NotificationChecker] Все уведомления истекли")
                return
            
            # Группируем уведомления по crypto_id
            notifications_by_crypto: Dict[str, List[Notification]] = defaultdict(list)
            for notification in valid_notifications:
                notifications_by_crypto[notification.crypto_id].append(notification)
            
            print(f"[NotificationChecker] Уникальных криптовалют: {len(notifications_by_crypto)}")
            
            # Проверяем каждую криптовалюту один раз
            for crypto_id, notifications in notifications_by_crypto.items():
                # Получаем текущую цену (с кэшированием)
                current_price = await self._get_crypto_price(crypto_id)
                
                if current_price is None:
                    print(f"[NotificationChecker] Пропускаю {len(notifications)} уведомлений для {crypto_id} (не удалось получить цену)")
                    continue
                
                # Проверяем все уведомления для этой криптовалюты
                for notification in notifications:
                    await self._check_and_process_notification(notification, current_price, db)
                
                # Небольшая задержка между криптовалютами
                await asyncio.sleep(0.5)
        
        finally:
            db.close()
    
    async def start(self):
        """Запустить периодическую проверку уведомлений"""
        self.running = True
        print(f"[NotificationChecker] 🚀 Запущена проверка уведомлений (интервал: {self.check_interval} сек)")
        
        while self.running:
            try:
                await self.check_all_notifications()
            except Exception as e:
                import traceback
                print(f"[NotificationChecker] Критическая ошибка: {str(e)}")
                print(f"[NotificationChecker] Traceback: {traceback.format_exc()}")
            
            # Ждем перед следующей проверкой
            await asyncio.sleep(self.check_interval)
    
    def stop(self):
        """Остановить проверку уведомлений"""
        self.running = False
        print("[NotificationChecker] ⏹️ Остановлена проверка уведомлений")
    


# Глобальный экземпляр
notification_checker = NotificationChecker()

