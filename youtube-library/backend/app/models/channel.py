import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False, unique=True)
    youtube_id = Column(String(64), nullable=True)
    # Only track the newest N videos (e.g. for playlists); NULL = all
    max_videos = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime, nullable=True)

    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Channel {self.name}>"
