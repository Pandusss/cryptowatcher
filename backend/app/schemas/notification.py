from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.models.notification import (
    NotificationDirection,
    NotificationTrigger,
    NotificationValueType,
)


class NotificationBase(BaseModel):
    crypto_id: str
    crypto_symbol: str
    crypto_name: str
    direction: NotificationDirection
    trigger: NotificationTrigger
    value_type: NotificationValueType
    value: float
    current_price: float
    expire_time_hours: Optional[int] = None  # null means no expiration


class NotificationCreate(NotificationBase):
    user_id: int


class NotificationUpdate(BaseModel):
    direction: Optional[NotificationDirection] = None
    trigger: Optional[NotificationTrigger] = None
    value_type: Optional[NotificationValueType] = None
    value: Optional[float] = None
    is_active: Optional[bool] = None
    expire_time_hours: Optional[int] = None  # null means no expiration


class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_active: bool
    expire_time_hours: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    triggered_at: Optional[datetime] = None
    crypto_image_url: Optional[str] = None  # URL изображения монеты из CoinGecko

    class Config:
        from_attributes = True

