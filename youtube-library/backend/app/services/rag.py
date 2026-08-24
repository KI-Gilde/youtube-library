from typing import Optional

from app.config import get_settings
from app.services.embedding import get_qdrant_client, embed_text

settings = get_settings()


async def get_relevant_context(
    query: str,
    channel_id: Optional[str] = None,
    top_k: int = 5
) -> tuple[str, list[dict]]:
    """
    Retrieve relevant context from Qdrant for a query.

    Returns:
        Tuple of (context_text, sources)
    """
    # Generate query embedding
    query_embedding = await embed_text(query)

    # Search in Qdrant
    client = get_qdrant_client()

    # Build filter if channel_id is provided
    search_filter = None
    if channel_id:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="channel_id",
                    match=MatchValue(value=channel_id)
                )
            ]
        )

    results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_embedding,
        limit=top_k,
        query_filter=search_filter,
        with_payload=True
    )

    # Build context and sources
    context_parts = []
    sources = []
    seen_videos = set()

    for result in results.points:
        payload = result.payload
        text = payload.get("text", "")
        video_id = payload.get("youtube_id", "")
        title = payload.get("title", "Unknown")

        context_parts.append(f"[From: {title}]\n{text}")

        # Add unique video sources
        if video_id not in seen_videos:
            seen_videos.add(video_id)
            sources.append({
                "video_id": payload.get("video_id"),
                "youtube_id": video_id,
                "title": title,
                "score": result.score
            })

    context = "\n\n---\n\n".join(context_parts)
    return context, sources


async def search_transcripts(
    query: str,
    channel_id: Optional[str] = None,
    top_k: int = 10
) -> list[dict]:
    """
    Search transcripts and return matching chunks.
    """
    query_embedding = await embed_text(query)

    client = get_qdrant_client()

    search_filter = None
    if channel_id:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="channel_id",
                    match=MatchValue(value=channel_id)
                )
            ]
        )

    results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_embedding,
        limit=top_k,
        query_filter=search_filter,
        with_payload=True
    )

    matches = []
    for result in results.points:
        payload = result.payload
        matches.append({
            "video_id": payload.get("video_id"),
            "youtube_id": payload.get("youtube_id"),
            "title": payload.get("title"),
            "text": payload.get("text"),
            "score": result.score
        })

    return matches
