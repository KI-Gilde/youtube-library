"""
Summary generation service using local LLM.
Generates concise summaries from video transcripts.
"""

from pathlib import Path
from uuid import UUID

from app.config import get_settings
from app.database import SessionLocal
from app.models import Video, VideoStatus
from app.services.llm import chat_completion

settings = get_settings()

SUMMARY_PROMPT = """Du bist ein Experte fuer Zusammenfassungen von technischen Videos.
Erstelle eine kurze Zusammenfassung des folgenden Video-Transkripts.

Anforderungen:
- Maximal 2-4 Saetze
- Fokus auf Hauptthema und wichtigste Erkenntnisse
- Klare, praegnante Sprache
- Antworte NUR mit der Zusammenfassung, keine Erklaerungen

Transkript:
{transcript}"""


async def generate_summary_with_llm(transcript: str) -> str | None:
    """Generate summary using the LLM API."""
    # Truncate very long transcripts
    truncated = transcript[:4000] if len(transcript) > 4000 else transcript

    try:
        content = await chat_completion(
            messages=[
                {"role": "user", "content": SUMMARY_PROMPT.format(transcript=truncated)}
            ],
            model=settings.llm_utility_model,
            temperature=0.3,
            max_tokens=256,
        )
        return content if len(content) > 20 else None

    except Exception as e:
        print(f"LLM summary error: {e}")
        return None


def create_fallback_summary(transcript: str, max_length: int = 200) -> str:
    """Create a simple excerpt-based fallback summary."""
    clean = transcript.strip()
    if len(clean) <= max_length:
        return clean

    # Try to break at sentence boundary
    truncated = clean[:max_length]
    last_period = truncated.rfind('.')
    if last_period > max_length // 2:
        return truncated[:last_period + 1]

    return truncated + "..."


async def generate_summary(video_id: UUID) -> str | None:
    """Generate and store a summary for a video."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return None

        # Need transcript to generate summary
        transcript_path = video.refined_transcript_path or video.transcript_path
        if not transcript_path:
            return None

        video.status = VideoStatus.SUMMARIZING
        db.commit()

        print(f"Generating summary: {video.title[:50]}...")

        # Read transcript
        try:
            transcript = Path(transcript_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"Transcript file not found: {transcript_path}")
            return None

        # Skip very short transcripts
        if len(transcript.strip()) < 50:
            video.summary = transcript.strip()
            db.commit()
            return video.summary

        # Try LLM-generated summary
        summary = await generate_summary_with_llm(transcript)

        # Fallback to excerpt if LLM fails
        if not summary:
            print(f"Using fallback summary for {video.youtube_id}")
            summary = create_fallback_summary(transcript)

        # Store summary
        video.summary = summary
        db.commit()

        print(f"Summary generated: {video.title[:50]} ({len(summary)} chars)")
        return summary

    except Exception as e:
        print(f"Error generating summary for {video_id}: {e}")
        return None
    finally:
        db.close()
