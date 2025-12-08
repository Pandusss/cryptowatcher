from sqlalchemy import Column, BigInteger, String, Integer, Float, Enum, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class NotificationDirection(str, enum.Enum):
    RISE = "rise"
    FALL = "fall"
    BOTH = "both"


class NotificationTrigger(str, enum.Enum):
    STOP_LOSS = "stop-loss"
    TAKE_PROFIT = "take-profit"


class NotificationValueType(str, enum.Enum):
    PERCENT = "percent"
    ABSOLUTE = "absolute"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    
    # Crypto info
    crypto_id = Column(String, nullable=False)  # CoinMarketCap ID
    crypto_symbol = Column(String, nullable=False)
    crypto_name = Column(String, nullable=False)
    
    # Notification settings
    direction = Column(Enum(NotificationDirection), nullable=False)
    trigger = Column(Enum(NotificationTrigger), nullable=False)
    value_type = Column(Enum(NotificationValueType), nullable=False)
    value = Column(Float, nullable=False)  # Percent or absolute value
    
    # Current price at creation
    current_price = Column(Float, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Expiration time (in hours, null means no expiration)
    expire_time_hours = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", backref="notifications")

