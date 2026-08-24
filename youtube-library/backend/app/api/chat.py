from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import json

from app.database import get_db
from app.config import get_settings

router = APIRouter()
settings = get_settings()


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    channel_id: Optional[str] = None  # Filter by channel


class ChatResponse(BaseModel):
    response: str
    sources: list[dict]


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    from app.services.rag import get_relevant_context
    from app.services.llm import generate_response

    # Get relevant context from RAG
    context, sources = await get_relevant_context(
        query=request.message,
        channel_id=request.channel_id
    )

    # Generate response
    response = await generate_response(
        query=request.message,
        context=context,
        history=request.history
    )

    return ChatResponse(response=response, sources=sources)


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    from app.services.rag import get_relevant_context
    from app.services.llm import generate_response_stream

    # Get relevant context from RAG
    context, sources = await get_relevant_context(
        query=request.message,
        channel_id=request.channel_id
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        # First, send sources
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        # Then stream the response
        async for chunk in generate_response_stream(
            query=request.message,
            context=context,
            history=request.history
        ):
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )
