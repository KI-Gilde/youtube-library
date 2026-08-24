from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import Channel, Video

router = APIRouter()


class ChannelCreate(BaseModel):
    url: str
    name: Optional[str] = None
    # Only track the newest N videos (useful for playlists); None = all
    max_videos: Optional[int] = None


class ChannelResponse(BaseModel):
    id: UUID
    name: str
    url: str
    youtube_id: Optional[str]
    created_at: datetime
    last_checked: Optional[datetime]
    video_count: int

    class Config:
        from_attributes = True


class ChannelList(BaseModel):
    channels: list[ChannelResponse]
    total: int


@router.get("", response_model=ChannelList)
def list_channels(db: Session = Depends(get_db)):
    channels = db.query(Channel).order_by(Channel.created_at.desc()).all()
    result = []
    for ch in channels:
        video_count = db.query(Video).filter(Video.channel_id == ch.id).count()
        result.append(ChannelResponse(
            id=ch.id,
            name=ch.name,
            url=ch.url,
            youtube_id=ch.youtube_id,
            created_at=ch.created_at,
            last_checked=ch.last_checked,
            video_count=video_count
        ))
    return ChannelList(channels=result, total=len(result))


@router.post("", response_model=ChannelResponse)
async def add_channel(
    channel: ChannelCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Check if channel already exists
    existing = db.query(Channel).filter(Channel.url == channel.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel already exists")

    # Import here to avoid circular imports
    from app.services.youtube import get_channel_info, fetch_channel_videos

    # Get channel info
    channel_info = await get_channel_info(channel.url)
    if not channel_info:
        raise HTTPException(status_code=400, detail="Could not fetch channel info")

    # Create channel
    db_channel = Channel(
        name=channel.name or channel_info["name"],
        url=channel.url,
        youtube_id=channel_info.get("id"),
        max_videos=channel.max_videos
    )
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)

    # Fetch videos in background
    background_tasks.add_task(fetch_channel_videos, db_channel.id)

    return ChannelResponse(
        id=db_channel.id,
        name=db_channel.name,
        url=db_channel.url,
        youtube_id=db_channel.youtube_id,
        created_at=db_channel.created_at,
        last_checked=db_channel.last_checked,
        video_count=0
    )


@router.get("/{channel_id}", response_model=ChannelResponse)
def get_channel(channel_id: UUID, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    video_count = db.query(Video).filter(Video.channel_id == channel.id).count()
    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        url=channel.url,
        youtube_id=channel.youtube_id,
        created_at=channel.created_at,
        last_checked=channel.last_checked,
        video_count=video_count
    )


@router.delete("/{channel_id}")
def delete_channel(channel_id: UUID, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    db.delete(channel)
    db.commit()
    return {"message": "Channel deleted"}


@router.post("/{channel_id}/refresh")
async def refresh_channel(
    channel_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    from app.services.youtube import fetch_channel_videos
    background_tasks.add_task(fetch_channel_videos, channel_id)

    return {"message": "Refresh started"}
