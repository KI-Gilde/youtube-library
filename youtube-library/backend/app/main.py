from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, SessionLocal
from app.api import api_router
from app.models import Video, VideoStatus

settings = get_settings()


def reset_stuck_videos():
    """Reset videos stuck in processing states back to PENDING.

    This handles cases where the backend was restarted while videos
    were being processed (DOWNLOADING, TRANSCRIBING, EMBEDDING).
    """
    db = SessionLocal()
    try:
        stuck_statuses = [
            VideoStatus.DOWNLOADING,
            VideoStatus.TRANSCRIBING,
            VideoStatus.REFINING,
            VideoStatus.SUMMARIZING,
            VideoStatus.EMBEDDING,
        ]

        stuck_videos = db.query(Video).filter(Video.status.in_(stuck_statuses)).all()

        if stuck_videos:
            print(f"Found {len(stuck_videos)} stuck videos, resetting to PENDING...")
            for video in stuck_videos:
                print(f"  - Resetting: {video.title[:50]}... ({video.status.value})")
                video.status = VideoStatus.PENDING
                video.error_message = None
            db.commit()
            print("Stuck videos reset successfully.")
        else:
            print("No stuck videos found.")

    except Exception as e:
        print(f"Error resetting stuck videos: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting YouTube Library Backend...")
    init_db()
    print("Database initialized.")

    # Reset any stuck videos from previous interrupted runs
    reset_stuck_videos()

    # Initialize scheduler
    from app.scheduler.jobs import start_scheduler
    start_scheduler()
    print("Scheduler started.")

    # Initialize embedding backend (Qdrant collection; embeddings via LLM API)
    from app.services.embedding import init_embedding_model
    await init_embedding_model()
    print("Embedding backend ready.")

    yield

    # Shutdown
    from app.scheduler.jobs import stop_scheduler
    stop_scheduler()
    print("Scheduler stopped.")


app = FastAPI(
    title="YouTube Library API",
    description="API for managing YouTube video library with RAG capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9070", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/")
def root():
    return {
        "name": "YouTube Library API",
        "version": "1.0.0",
        "docs": "/docs"
    }
