import asyncio
from pathlib import Path
from uuid import UUID

from faster_whisper import WhisperModel

from app.config import get_settings
from app.database import SessionLocal
from app.models import Video, VideoStatus

settings = get_settings()

# Global model instance
_whisper_model = None


def get_whisper_model() -> WhisperModel:
    """Get or create Whisper model instance."""
    global _whisper_model
    if _whisper_model is None:
        print(f"Loading Whisper model: {settings.whisper_model}")
        _whisper_model = WhisperModel(
            settings.whisper_model,
            device="auto",  # Will use CUDA if available
            compute_type="auto"
        )
        print("Whisper model loaded.")
    return _whisper_model


async def transcribe_audio(audio_path: str) -> str:
    """Transcribe an audio file using Whisper."""
    model = get_whisper_model()

    def _transcribe():
        segments, info = model.transcribe(
            audio_path,
            beam_size=5,
            language=None,  # Auto-detect
            vad_filter=True
        )
        # Combine all segments into full text
        text = " ".join([segment.text.strip() for segment in segments])
        return text

    return await asyncio.to_thread(_transcribe)


async def transcribe_video(video_id: UUID) -> str | None:
    """Transcribe a video's audio file."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video or not video.audio_path:
            return None

        video.status = VideoStatus.TRANSCRIBING
        db.commit()

        print(f"Transcribing: {video.title[:50]}...")

        # Transcribe
        text = await transcribe_audio(video.audio_path)

        # Save transcript
        data_dir = Path(settings.data_dir)
        transcript_dir = data_dir / "transcripts"
        transcript_dir.mkdir(parents=True, exist_ok=True)

        transcript_path = transcript_dir / f"{video.youtube_id}.txt"
        transcript_path.write_text(text, encoding="utf-8")

        # Update database
        video.transcript_path = str(transcript_path)
        db.commit()

        print(f"Transcribed: {video.title[:50]} ({len(text)} chars)")
        return text

    except Exception as e:
        print(f"Error transcribing video {video_id}: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = VideoStatus.ERROR
            video.error_message = f"Transcription error: {e}"
            db.commit()
        return None
    finally:
        db.close()
