from fastapi import APIRouter

from app.api.v1.endpoints import coins, notifications, users, bot

api_router = APIRouter()

api_router.include_router(coins.router, prefix="/coins", tags=["coins"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(bot.router, prefix="/bot", tags=["bot"])

