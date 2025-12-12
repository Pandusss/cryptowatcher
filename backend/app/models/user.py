from sqlalchemy import Column, BigInteger, String, DateTime, Boolean, Time
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    language_code = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    # Don't Disturb settings (time in UTC)
    dnd_start_time = Column(Time, nullable=True)  # Start time for DND (e.g., 12:00)
    dnd_end_time = Column(Time, nullable=True)  # End time for DND (e.g., 07:00)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

