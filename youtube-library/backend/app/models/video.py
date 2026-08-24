import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class VideoStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    REFINING = "refining"
    SUMMARIZING = "summarizing"
    EMBEDDING = "embedding"
    DONE = "done"
    ERROR = "error"


class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    youtube_id = Column(String(11), nullable=False, unique=True)
    title = Column(String(512), nullable=False)
    status = Column(SQLEnum(VideoStatus), default=VideoStatus.PENDING)
    error_message = Column(String(1024), nullable=True)

    # File paths
    video_path = Column(String(512), nullable=True)
    audio_path = Column(String(512), nullable=True)
    transcript_path = Column(String(512), nullable=True)
    refined_transcript_path = Column(String(512), nullable=True)
    thumbnail_path = Column(String(512), nullable=True)

    # AI-generated content
    summary = Column(String(4096), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    channel = relationship("Channel", back_populates="videos")

    def __repr__(self):
        return f"<Video {self.title[:30]}>"
