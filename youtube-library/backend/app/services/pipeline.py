import asyncio
from datetime import datetime
from uuid import UUID

from app.database import SessionLocal
from app.models import Video, VideoStatus
from app.services.youtube import download_video, download_thumbnail
from app.services.transcription import transcribe_video
from app.services.refinement import refine_transcript
from app.services.summary import generate_summary
from app.services.embedding import embed_video_transcript

# Lock to prevent parallel processing
_processing_lock = asyncio.Lock()

# Current processing state
_current_video_id: UUID | None = None
_current_step: str | None = None


def is_processing() -> bool:
    """Check if video processing is currently running."""
    return _processing_lock.locked()


def get_processing_status() -> dict:
    """Get current processing status."""
    return {
        "is_processing": _processing_lock.locked(),
        "current_video_id": str(_current_video_id) if _current_video_id else None,
        "current_step": _current_step,
    }


def _set_current_step(video_id: UUID | None, step: str | None):
    """Update current processing step."""
    global _current_video_id, _current_step
    _current_video_id = video_id
    _current_step = step


async def process_video(video_id: UUID) -> bool:
    """
    Process a single video through the full pipeline:
    Download -> Thumbnail -> Transcribe -> Refine -> Summarize -> Embed
    """
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return False

        print(f"Processing video: {video.title[:50]}...")
        _set_current_step(video_id, "downloading")

        # Step 1: Download
        if not video.audio_path:
            video_path, audio_path = await download_video(video_id)
            if not audio_path:
                return False

        # Step 1.5: Download thumbnail (non-critical)
        if not video.thumbnail_path:
            await download_thumbnail(video_id)

        # Refresh video from DB
        db.refresh(video)

        # Step 2: Transcribe
        _set_current_step(video_id, "transcribing")
        if not video.transcript_path:
            transcript = await transcribe_video(video_id)
            if not transcript:
                return False

        # Refresh video from DB
        db.refresh(video)

        # Step 3: Refine
        _set_current_step(video_id, "refining")
        if not video.refined_transcript_path:
            refined = await refine_transcript(video_id)
            # Not critical if refinement fails

        # Refresh video from DB
        db.refresh(video)

        # Step 3.5: Generate summary (non-critical)
        _set_current_step(video_id, "summarizing")
        if not video.summary:
            await generate_summary(video_id)

        # Refresh video from DB
        db.refresh(video)

        # Step 4: Embed
        _set_current_step(video_id, "embedding")
        success = await embed_video_transcript(video_id)
        if not success:
            return False

        # Mark as done
        video.status = VideoStatus.DONE
        video.processed_at = datetime.utcnow()
        db.commit()

        print(f"Completed: {video.title[:50]}")
        _set_current_step(None, None)
        return True

    except Exception as e:
        print(f"Error in pipeline for video {video_id}: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = VideoStatus.ERROR
            video.error_message = str(e)
            db.commit()
        _set_current_step(None, None)
        return False
    finally:
        db.close()


async def process_pending_videos(channel_id: UUID | None = None) -> int:
    """
    Process all pending videos, optionally filtered by channel.
    Returns the number of successfully processed videos.
    Uses a lock to prevent parallel processing.
    """
    # Try to acquire lock without blocking
    if _processing_lock.locked():
        print("Processing already in progress, skipping...")
        return 0

    async with _processing_lock:
        success_count = 0
        attempted_ids: set[UUID] = set()

        # Keep draining the queue so videos added mid-run are picked up too.
        # Each video is attempted at most once per run to guarantee termination.
        while True:
            db = SessionLocal()
            try:
                query = db.query(Video).filter(Video.status == VideoStatus.PENDING)
                if channel_id:
                    query = query.filter(Video.channel_id == channel_id)
                pending_ids = [v.id for v in query.all() if v.id not in attempted_ids]
            finally:
                db.close()

            if not pending_ids:
                break

            print(f"Found {len(pending_ids)} pending videos to process")
            for video_id in pending_ids:
                attempted_ids.add(video_id)
                try:
                    if await process_video(video_id):
                        success_count += 1
                except Exception as e:
                    print(f"Error processing video {video_id}: {e}")

        return success_count


async def reprocess_failed_videos() -> int:
    """Retry processing for failed videos."""
    db = SessionLocal()
    try:
        failed_count = db.query(Video).filter(
            Video.status == VideoStatus.ERROR
        ).update(
            {"status": VideoStatus.PENDING, "error_message": None},
            synchronize_session=False,
        )
        db.commit()
        print(f"Found {failed_count} failed videos to retry")
    finally:
        db.close()

    return await process_pending_videos()
