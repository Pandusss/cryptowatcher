from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import asyncio

from app.core.database import get_db
from app.models.user import User
from app.services.user_service import get_or_create_user

router = APIRouter()


class UserCreateRequest(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Получить пользователя по ID"""
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
    """Создать или обновить пользователя из Telegram WebApp"""
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
    """Регистрация пользователя (алиас для create_or_update_user)"""
    return await create_or_update_user(user_data, db)

