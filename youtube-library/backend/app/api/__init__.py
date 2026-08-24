from fastapi import APIRouter
from app.api import channels, videos, chat

api_router = APIRouter()

api_router.include_router(channels.router, prefix="/channels", tags=["channels"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
