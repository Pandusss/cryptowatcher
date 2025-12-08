from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import asyncio

from app.core.database import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationUpdate, NotificationResponse
from app.services.user_service import get_or_create_user

router = APIRouter()


@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Получить список уведомлений пользователя"""
    # Выполняем синхронный DB запрос в отдельном потоке, чтобы не блокировать event loop
    loop = asyncio.get_event_loop()
    notifications = await loop.run_in_executor(
        None,
        lambda: db.query(Notification).filter(Notification.user_id == user_id).all()
    )
    return notifications


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
):
    """Получить одно уведомление по ID"""
    loop = asyncio.get_event_loop()
    notification = await loop.run_in_executor(
        None,
        lambda: db.query(Notification).filter(Notification.id == notification_id).first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.post("/", response_model=NotificationResponse)
async def create_notification(
    notification: NotificationCreate,
    db: Session = Depends(get_db),
):
    """Создать новое уведомление"""
    loop = asyncio.get_event_loop()
    
    # Автоматически создаем пользователя, если его нет
    await loop.run_in_executor(
        None,
        lambda: get_or_create_user(
            db=db,
            user_id=notification.user_id,
        )
    )
    
    def _create():
        db_notification = Notification(**notification.dict())
        db.add(db_notification)
        db.commit()
        db.refresh(db_notification)
        return db_notification
    
    db_notification = await loop.run_in_executor(None, _create)
    return db_notification


@router.put("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: int,
    notification: NotificationUpdate,
    db: Session = Depends(get_db),
):
    """Обновить уведомление"""
    loop = asyncio.get_event_loop()
    
    db_notification = await loop.run_in_executor(
        None,
        lambda: db.query(Notification).filter(Notification.id == notification_id).first()
    )
    if not db_notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    def _update():
        for key, value in notification.dict(exclude_unset=True).items():
            setattr(db_notification, key, value)
        db.commit()
        db.refresh(db_notification)
        return db_notification
    
    db_notification = await loop.run_in_executor(None, _update)
    return db_notification


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
):
    """Удалить уведомление"""
    loop = asyncio.get_event_loop()
    
    db_notification = await loop.run_in_executor(
        None,
        lambda: db.query(Notification).filter(Notification.id == notification_id).first()
    )
    if not db_notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    def _delete():
        db.delete(db_notification)
        db.commit()
        return {"message": "Notification deleted"}
    
    return await loop.run_in_executor(None, _delete)

