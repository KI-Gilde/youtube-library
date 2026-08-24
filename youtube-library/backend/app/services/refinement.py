from pathlib import Path
from uuid import UUID

from app.config import get_settings
from app.database import SessionLocal
from app.models import Video, VideoStatus
from app.services.llm import chat_completion
from app.services.prompts import refine_prompt

settings = get_settings()


def chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    sentences = text.replace('. ', '.|').replace('? ', '?|').replace('! ', '!|').split('|')

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


async def refine_with_llm(text: str) -> str:
    """Refine transcript text using the LLM API."""
    chunks = chunk_text(text)
    refined_chunks = []

    for i, chunk in enumerate(chunks):
        try:
            refined = await chat_completion(
                messages=[
                    {"role": "system", "content": refine_prompt()},
                    {"role": "user", "content": chunk},
                ],
                model=settings.llm_utility_model,
                temperature=0.2,
                max_tokens=4096,
                timeout=300.0,
            )

            if refined and len(refined) > len(chunk) * 0.5:
                refined_chunks.append(refined)
            else:
                refined_chunks.append(chunk)

            if len(chunks) > 1:
                print(f"  Chunk {i+1}/{len(chunks)} refined")

        except Exception as e:
            print(f"Error refining chunk {i+1}: {e}")
            refined_chunks.append(chunk)

    return " ".join(refined_chunks)


async def refine_transcript(video_id: UUID) -> str | None:
    """Refine a video's transcript."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video or not video.transcript_path:
            return None

        video.status = VideoStatus.REFINING
        db.commit()

        print(f"Refining: {video.title[:50]}...")

        # Read original transcript
        transcript = Path(video.transcript_path).read_text(encoding="utf-8")

        # Skip very short transcripts
        if len(transcript.strip()) < 100:
            refined = transcript
        else:
            refined = await refine_with_llm(transcript)

        # Save refined transcript
        data_dir = Path(settings.data_dir)
        refined_dir = data_dir / "transcripts_refined"
        refined_dir.mkdir(parents=True, exist_ok=True)

        refined_path = refined_dir / f"{video.youtube_id}.txt"
        refined_path.write_text(refined, encoding="utf-8")

        # Update database
        video.refined_transcript_path = str(refined_path)
        db.commit()

        print(f"Refined: {video.title[:50]} ({len(transcript)} -> {len(refined)} chars)")
        return refined

    except Exception as e:
        print(f"Error refining video {video_id}: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = VideoStatus.ERROR
            video.error_message = f"Refinement error: {e}"
            db.commit()
        return None
    finally:
        db.close()
