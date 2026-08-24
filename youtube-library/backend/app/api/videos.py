from uuid import UUID
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Header
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import case
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import Video, VideoStatus, Channel

router = APIRouter()


class VideoResponse(BaseModel):
    id: UUID
    channel_id: UUID
    channel_name: str
    youtube_id: str
    title: str
    status: VideoStatus
    error_message: Optional[str]
    video_path: Optional[str]
    audio_path: Optional[str]
    transcript_path: Optional[str]
    refined_transcript_path: Optional[str]
    thumbnail_path: Optional[str]
    summary: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class VideoList(BaseModel):
    videos: list[VideoResponse]
    total: int
    page: int
    per_page: int


class VideoSearchResult(BaseModel):
    id: UUID
    channel_id: UUID
    channel_name: str
    youtube_id: str
    title: str
    thumbnail_path: Optional[str]
    summary: Optional[str]
    score: float
    matching_text: str

    class Config:
        from_attributes = True


class VideoSearchResponse(BaseModel):
    results: list[VideoSearchResult]
    query: str
    total: int


@router.get("", response_model=VideoList)
def list_videos(
    channel_id: Optional[UUID] = None,
    status: Optional[VideoStatus] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(Video).join(Channel)

    if channel_id:
        query = query.filter(Video.channel_id == channel_id)
    if status:
        query = query.filter(Video.status == status)

    total = query.count()

    # Sort by status priority: DONE first, then processing, then pending, errors last
    status_order = case(
        (Video.status == VideoStatus.DONE, 1),
        (Video.status == VideoStatus.EMBEDDING, 2),
        (Video.status == VideoStatus.TRANSCRIBING, 3),
        (Video.status == VideoStatus.DOWNLOADING, 4),
        (Video.status == VideoStatus.PENDING, 5),
        (Video.status == VideoStatus.ERROR, 6),
        else_=7
    )

    videos = query.order_by(status_order, Video.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for v in videos:
        result.append(VideoResponse(
            id=v.id,
            channel_id=v.channel_id,
            channel_name=v.channel.name,
            youtube_id=v.youtube_id,
            title=v.title,
            status=v.status,
            error_message=v.error_message,
            video_path=v.video_path,
            audio_path=v.audio_path,
            transcript_path=v.transcript_path,
            refined_transcript_path=v.refined_transcript_path,
            thumbnail_path=v.thumbnail_path,
            summary=v.summary,
            created_at=v.created_at,
            processed_at=v.processed_at
        ))

    return VideoList(videos=result, total=total, page=page, per_page=per_page)


@router.get("/search", response_model=VideoSearchResponse)
async def search_videos(
    q: str = Query(..., min_length=1, description="Search query"),
    channel_id: Optional[UUID] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Semantic search across video transcripts using RAG."""
    from app.services.embedding import embed_text, get_qdrant_client
    from app.config import get_settings

    settings = get_settings()

    # Generate embedding for query
    query_embedding = await embed_text(q)

    # Search in Qdrant
    client = get_qdrant_client()

    # Build filter if channel_id provided
    search_filter = None
    if channel_id:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="channel_id",
                    match=MatchValue(value=str(channel_id))
                )
            ]
        )

    search_results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_embedding,
        limit=limit * 3,  # Get more results to account for deduplication
        query_filter=search_filter,
        with_payload=True
    ).points

    # Deduplicate by video_id, keeping highest score
    video_scores: dict[str, tuple[float, str]] = {}
    for result in search_results:
        video_id = result.payload.get("video_id")
        if video_id:
            if video_id not in video_scores or result.score > video_scores[video_id][0]:
                video_scores[video_id] = (result.score, result.payload.get("text", ""))

    # Get video details from database
    results = []
    for video_id_str, (score, matching_text) in sorted(
        video_scores.items(), key=lambda x: x[1][0], reverse=True
    )[:limit]:
        try:
            video = db.query(Video).filter(Video.id == UUID(video_id_str)).first()
            if video and video.status == VideoStatus.DONE:
                results.append(VideoSearchResult(
                    id=video.id,
                    channel_id=video.channel_id,
                    channel_name=video.channel.name,
                    youtube_id=video.youtube_id,
                    title=video.title,
                    thumbnail_path=video.thumbnail_path,
                    summary=video.summary,
                    score=round(score, 3),
                    matching_text=matching_text[:300] + "..." if len(matching_text) > 300 else matching_text
                ))
        except Exception:
            continue

    return VideoSearchResponse(results=results, query=q, total=len(results))


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: UUID, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return VideoResponse(
        id=video.id,
        channel_id=video.channel_id,
        channel_name=video.channel.name,
        youtube_id=video.youtube_id,
        title=video.title,
        status=video.status,
        error_message=video.error_message,
        video_path=video.video_path,
        audio_path=video.audio_path,
        transcript_path=video.transcript_path,
        refined_transcript_path=video.refined_transcript_path,
        thumbnail_path=video.thumbnail_path,
        summary=video.summary,
        created_at=video.created_at,
        processed_at=video.processed_at
    )


@router.get("/{video_id}/transcript")
def get_transcript(video_id: UUID, refined: bool = True, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    path = video.refined_transcript_path if refined else video.transcript_path
    if not path:
        raise HTTPException(status_code=404, detail="Transcript not available")

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"transcript": content, "refined": refined}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Transcript file not found")


@router.post("/{video_id}/reprocess")
async def reprocess_video(
    video_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Reset status
    video.status = VideoStatus.PENDING
    video.error_message = None
    db.commit()

    # Route through the queue so the processing lock is respected
    from app.services.pipeline import process_pending_videos
    background_tasks.add_task(process_pending_videos, video.channel_id)

    return {"message": "Reprocessing started"}


@router.delete("/{video_id}")
def delete_video(video_id: UUID, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    db.delete(video)
    db.commit()
    return {"message": "Video deleted"}


@router.get("/stats/summary")
def get_stats(db: Session = Depends(get_db)):
    total_videos = db.query(Video).count()
    by_status = {}
    for status in VideoStatus:
        count = db.query(Video).filter(Video.status == status).count()
        by_status[status.value] = count

    return {
        "total_videos": total_videos,
        "by_status": by_status
    }


@router.get("/process/status")
def get_processing_status(db: Session = Depends(get_db)):
    """Get current processing status including which video is being processed."""
    from app.services.pipeline import get_processing_status

    status = get_processing_status()

    # If processing, get video details
    current_video = None
    if status["current_video_id"]:
        video = db.query(Video).filter(Video.id == status["current_video_id"]).first()
        if video:
            current_video = {
                "id": str(video.id),
                "title": video.title,
                "channel_name": video.channel.name if video.channel else None,
                "youtube_id": video.youtube_id,
            }

    return {
        "is_processing": status["is_processing"],
        "current_step": status["current_step"],
        "current_video": current_video,
    }


@router.post("/process/start")
async def start_processing(
    background_tasks: BackgroundTasks,
    channel_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    """Start processing pending videos in the background."""
    from app.services.pipeline import process_pending_videos, is_processing

    # Check if already processing
    if is_processing():
        return {"message": "Processing already in progress", "pending": 0, "already_running": True}

    # Count pending videos
    query = db.query(Video).filter(Video.status == VideoStatus.PENDING)
    if channel_id:
        query = query.filter(Video.channel_id == channel_id)
    pending_count = query.count()

    if pending_count == 0:
        return {"message": "No pending videos to process", "pending": 0}

    # Start processing in background
    background_tasks.add_task(process_pending_videos, channel_id)

    return {"message": f"Started processing {pending_count} pending videos", "pending": pending_count}


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: UUID,
    range: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Stream video file with range request support for seeking."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.video_path:
        raise HTTPException(status_code=404, detail="Video file not available")

    video_path = Path(video.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    file_size = video_path.stat().st_size

    # Handle range requests for seeking
    if range:
        # Parse range header: "bytes=start-end"
        range_match = range.replace("bytes=", "").split("-")
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1

        if start >= file_size:
            raise HTTPException(status_code=416, detail="Range not satisfiable")

        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iterfile():
            with open(video_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(65536, remaining)  # 64KB chunks
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iterfile(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
            }
        )

    # Full file response
    return FileResponse(
        video_path,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        }
    )


@router.get("/{video_id}/thumbnail")
async def get_thumbnail(video_id: UUID, db: Session = Depends(get_db)):
    """Get video thumbnail image."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    thumbnail_path = Path(video.thumbnail_path)
    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found")

    return FileResponse(
        thumbnail_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"}
    )
