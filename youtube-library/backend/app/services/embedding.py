import uuid
from pathlib import Path
from uuid import UUID
from typing import Optional

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings
from app.database import SessionLocal
from app.models import Video, VideoStatus

settings = get_settings()

# Embeddings come from the OpenAI-compatible LLM API (bge-m3, 1024 dims) —
# no local model is loaded anymore.
EMBEDDING_BATCH_SIZE = 32

_qdrant_client: Optional[QdrantClient] = None


async def init_embedding_model():
    """Initialize the embedding backend (Qdrant collection; embeddings are remote)."""
    await init_qdrant_collection()


def get_qdrant_client() -> QdrantClient:
    """Get or create Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port
        )
    return _qdrant_client


async def init_qdrant_collection():
    """Initialize the Qdrant collection for transcripts."""
    client = get_qdrant_client()

    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if settings.qdrant_collection not in collection_names:
        print(f"Creating Qdrant collection: {settings.qdrant_collection}")
        # BGE-M3 produces 1024-dimensional dense vectors
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=1024,
                distance=Distance.COSINE
            )
        )
        print("Qdrant collection created.")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)

    return chunks


async def _request_embeddings(texts: list[str]) -> list[list[float]]:
    """Fetch embeddings for a batch of texts from the LLM API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.llm_api_base}/embeddings",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={"model": settings.embedding_model, "input": texts},
        )
        response.raise_for_status()
        data = response.json()["data"]
        # Preserve input order regardless of response ordering
        data.sort(key=lambda item: item["index"])
        return [item["embedding"] for item in data]


async def embed_text(text: str) -> list[float]:
    """Generate embedding for a text."""
    embeddings = await _request_embeddings([text])
    return embeddings[0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts, batched per API request."""
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start:start + EMBEDDING_BATCH_SIZE]
        embeddings.extend(await _request_embeddings(batch))
    return embeddings


async def embed_video_transcript(video_id: UUID) -> bool:
    """Embed a video's transcript into Qdrant."""
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return False

        # Use refined transcript if available, else original
        transcript_path = video.refined_transcript_path or video.transcript_path
        if not transcript_path:
            return False

        video.status = VideoStatus.EMBEDDING
        db.commit()

        print(f"Embedding: {video.title[:50]}...")

        # Read transcript
        transcript = Path(transcript_path).read_text(encoding="utf-8")

        # Chunk the transcript
        chunks = chunk_text(transcript)
        if not chunks:
            return False

        # Generate embeddings
        embeddings = await embed_texts(chunks)

        # Store in Qdrant
        client = get_qdrant_client()

        # Drop any previous chunks of this video first, so re-embedding never
        # leaves duplicates or orphans behind
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=FilterSelector(
                filter=Filter(must=[
                    FieldCondition(key="video_id", match=MatchValue(value=str(video.id)))
                ])
            ),
        )

        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Deterministic ID: stable across restarts (unlike Python's hash())
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{video.youtube_id}_{i}"))
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "video_id": str(video.id),
                    "youtube_id": video.youtube_id,
                    "channel_id": str(video.channel_id),
                    "title": video.title,
                    "chunk_index": i,
                    "text": chunk
                }
            ))

        client.upsert(
            collection_name=settings.qdrant_collection,
            points=points
        )

        print(f"Embedded: {video.title[:50]} ({len(chunks)} chunks)")
        return True

    except Exception as e:
        print(f"Error embedding video {video_id}: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = VideoStatus.ERROR
            video.error_message = f"Embedding error: {e}"
            db.commit()
        return False
    finally:
        db.close()
