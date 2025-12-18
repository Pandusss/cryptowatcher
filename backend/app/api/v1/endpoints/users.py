from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import time
import asyncio
import logging

from app.core.database import get_db
from app.models.user import User
from app.services.user_service import get_or_create_user

router = APIRouter()
logger = logging.getLogger("EndpointsUsers")



class UserCreateRequest(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None


class DndSettingsUpdate(BaseModel):
    dnd_start_time: Optional[str] = None  # Format: "HH:MM" (e.g., "12:00")
    dnd_end_time: Optional[str] = None  # Format: "HH:MM" (e.g., "07:00")


class DndSettingsResponse(BaseModel):
    dnd_start_time: Optional[str] = None  # Format: "HH:MM"
    dnd_end_time: Optional[str] = None  # Format: "HH:MM"


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Get user by ID"""
    loop = asyncio.get_event_loop()
    user = await loop.run_in_executor(
        None,
        lambda: db.query(User).filter(User.id == user_id).first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/")
async def create_or_update_user(
    user_data: UserCreateRequest,
    db: Session = Depends(get_db),
):
    """Create or update user from Telegram WebApp"""
    loop = asyncio.get_event_loop()
    user = await loop.run_in_executor(
        None,
        lambda: get_or_create_user(
            db=db,
            user_id=user_data.id,
            username=user_data.username,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            language_code=user_data.language_code,
        )
    )
    return user


@router.post("/register")
async def register_user(
    user_data: UserCreateRequest,
    db: Session = Depends(get_db),
):
    """User registration (alias for create_or_update_user)"""
    return await create_or_update_user(user_data, db)


@router.put("/{user_id}/dnd-settings")
async def update_dnd_settings(
    user_id: int,
    settings: DndSettingsUpdate,
    db: Session = Depends(get_db),
):
    """Update Don't Disturb settings for user"""
    loop = asyncio.get_event_loop()
    
    def update_settings():
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Parse time from string "HH:MM"
        if settings.dnd_start_time is not None:
            try:
                hour, minute = map(int, settings.dnd_start_time.split(':'))
                user.dnd_start_time = time(hour, minute)
            except (ValueError, AttributeError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid start_time format. Use HH:MM. Got: {settings.dnd_start_time}")
        elif settings.dnd_start_time is None and hasattr(settings, 'dnd_start_time'):
            # If explicitly passed None, reset value
            user.dnd_start_time = None
        
        if settings.dnd_end_time is not None:
            try:
                hour, minute = map(int, settings.dnd_end_time.split(':'))
                user.dnd_end_time = time(hour, minute)
            except (ValueError, AttributeError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid end_time format. Use HH:MM. Got: {settings.dnd_end_time}")
        elif settings.dnd_end_time is None and hasattr(settings, 'dnd_end_time'):
            # If explicitly passed None, reset value
            user.dnd_end_time = None
        
        db.commit()
        db.refresh(user)
        return user
    
    try:
        user = await loop.run_in_executor(None, update_settings)
        
        # Format time for response
        result = DndSettingsResponse(
            dnd_start_time=user.dnd_start_time.strftime("%H:%M") if user.dnd_start_time else None,
            dnd_end_time=user.dnd_end_time.strftime("%H:%M") if user.dnd_end_time else None,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating DND settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{user_id}/dnd-settings")
async def get_dnd_settings(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Get Don't Disturb settings for user"""
    loop = asyncio.get_event_loop()
    user = await loop.run_in_executor(
        None,
        lambda: db.query(User).filter(User.id == user_id).first()
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return DndSettingsResponse(
        dnd_start_time=user.dnd_start_time.strftime("%H:%M") if user.dnd_start_time else None,
        dnd_end_time=user.dnd_end_time.strftime("%H:%M") if user.dnd_end_time else None,
    )