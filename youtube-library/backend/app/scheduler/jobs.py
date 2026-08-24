from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import SessionLocal
from app.models import Channel, Video, VideoStatus

settings = get_settings()

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def check_all_channels():
    """Check all channels for new videos."""
    print(f"[{datetime.now()}] Running scheduled channel check...")

    db = SessionLocal()
    try:
        channels = db.query(Channel).all()
        print(f"Checking {len(channels)} channels...")

        for channel in channels:
            try:
                from app.services.youtube import fetch_channel_videos
                await fetch_channel_videos(channel.id)
            except Exception as e:
                print(f"Error checking channel {channel.name}: {e}")

        print(f"[{datetime.now()}] Channel check completed.")

    except Exception as e:
        print(f"Error in scheduled check: {e}")
    finally:
        db.close()


async def process_pending():
    """Process any pending videos."""
    print(f"[{datetime.now()}] Processing pending videos...")

    try:
        from app.services.pipeline import process_pending_videos
        count = await process_pending_videos()
        print(f"Processed {count} videos.")
    except Exception as e:
        print(f"Error processing pending videos: {e}")


async def reset_stuck_videos():
    """Reset videos stuck in processing states.

    Only safe while the pipeline lock is free: every processing path goes
    through that lock, so any video still marked as in-progress then is a
    leftover from a crashed or interrupted run, not active work.
    """
    from app.services.pipeline import is_processing

    if is_processing():
        return

    db = SessionLocal()
    try:
        in_progress_statuses = [
            VideoStatus.DOWNLOADING,
            VideoStatus.TRANSCRIBING,
            VideoStatus.REFINING,
            VideoStatus.SUMMARIZING,
            VideoStatus.EMBEDDING,
        ]

        stuck_count = db.query(Video).filter(
            Video.status.in_(in_progress_statuses)
        ).update(
            {"status": VideoStatus.PENDING, "error_message": None},
            synchronize_session=False,
        )

        if stuck_count > 0:
            db.commit()
            print(f"[{datetime.now()}] Reset {stuck_count} stuck videos to pending")

    except Exception as e:
        print(f"Error resetting stuck videos: {e}")
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    """Start the background scheduler."""
    scheduler = get_scheduler()

    # Check channels every hour
    scheduler.add_job(
        check_all_channels,
        IntervalTrigger(hours=settings.check_interval_hours),
        id="check_channels",
        replace_existing=True,
        name="Check all channels for new videos"
    )

    # Process pending videos every 5 minutes
    scheduler.add_job(
        process_pending,
        IntervalTrigger(minutes=5),
        id="process_pending",
        replace_existing=True,
        name="Process pending videos"
    )

    # Reset stuck videos every 10 minutes
    scheduler.add_job(
        reset_stuck_videos,
        IntervalTrigger(minutes=10),
        id="reset_stuck",
        replace_existing=True,
        name="Reset stuck videos"
    )

    scheduler.start()
    print(f"Scheduler started. Checking channels every {settings.check_interval_hours} hour(s).")


def stop_scheduler():
    """Stop the scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown()
        print("Scheduler stopped.")
