from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
import asyncio
import logging

from app.core.database import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationUpdate, NotificationResponse
from app.services.user_service import get_or_create_user
from app.services.aggregation_service import aggregation_service

router = APIRouter()
logger = logging.getLogger("EndpointNotifications")


async def get_image_urls_for_notifications(notifications: List[Notification]) -> Dict[str, Optional[str]]:
    """Get image URLs for multiple notifications efficiently"""
    if not notifications:
        return {}
    
    unique_crypto_ids = list(set([n.crypto_id for n in notifications]))
    
    async def get_image_url(crypto_id: str):
        try:
            # aggregation_service already handles coin_registry checks internally
            image_url = await aggregation_service.get_coin_image_url(crypto_id)
            return crypto_id, image_url
        except Exception as e:
            logger.warning(f"Failed to get imageUrl for {crypto_id}: {e}")
            return crypto_id, None
    
    results = await asyncio.gather(
        *[get_image_url(crypto_id) for crypto_id in unique_crypto_ids],
        return_exceptions=True
    )
    
    image_urls = {}
    for result in results:
        if isinstance(result, tuple):
            crypto_id, image_url = result
            image_urls[crypto_id] = image_url
    
    return image_urls



@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Get list of active notifications for user"""
    # Execute synchronous DB query in separate thread to avoid blocking event loop
    loop = asyncio.get_event_loop()
    notifications = await loop.run_in_executor(
        None,
        lambda: db.query(Notification)
            .filter(Notification.user_id == user_id)
            .filter(Notification.is_active == True)  # Show only active notifications
            .all()
    )
    
    # Get image URLs for all notifications efficiently
    image_urls = await get_image_urls_for_notifications(notifications)
    
    # Add imageUrl to each notification
    notifications_with_images = []
    for notification in notifications:
        # Create dictionary from notification
        notification_dict = {
            "id": notification.id,
            "user_id": notification.user_id,
            "crypto_id": notification.crypto_id,
            "crypto_symbol": notification.crypto_symbol,
            "crypto_name": notification.crypto_name,
            "direction": notification.direction,
            "trigger": notification.trigger,
            "value_type": notification.value_type,
            "value": notification.value,
            "current_price": notification.current_price,
            "is_active": notification.is_active,
            "expire_time_hours": notification.expire_time_hours,
            "created_at": notification.created_at,
            "updated_at": notification.updated_at,
            "triggered_at": notification.triggered_at,
            "crypto_image_url": image_urls.get(notification.crypto_id),
        }
        notifications_with_images.append(NotificationResponse(**notification_dict))
    
    return notifications_with_images


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
):
    """Get single notification by ID"""
    loop = asyncio.get_event_loop()
    notification = await loop.run_in_executor(
        None,
        lambda: db.query(Notification).filter(Notification.id == notification_id).first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Get imageUrl using shared helper function
    image_urls = await get_image_urls_for_notifications([notification])
    image_url = image_urls.get(notification.crypto_id)
    
    # Create dictionary from notification with imageUrl
    notification_dict = {
        "id": notification.id,
        "user_id": notification.user_id,
        "crypto_id": notification.crypto_id,
        "crypto_symbol": notification.crypto_symbol,
        "crypto_name": notification.crypto_name,
        "direction": notification.direction,
        "trigger": notification.trigger,
        "value_type": notification.value_type,
        "value": notification.value,
        "current_price": notification.current_price,
        "is_active": notification.is_active,
        "expire_time_hours": notification.expire_time_hours,
        "created_at": notification.created_at,
        "updated_at": notification.updated_at,
        "triggered_at": notification.triggered_at,
        "crypto_image_url": image_url,
    }
    
    return NotificationResponse(**notification_dict)


@router.post("/", response_model=NotificationResponse)
async def create_notification(
    notification: NotificationCreate,
    db: Session = Depends(get_db),
):
    """Create new notification"""
    loop = asyncio.get_event_loop()
    
    # Automatically create user if doesn't exist
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
    """Update notification"""
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
    """Delete notification"""
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