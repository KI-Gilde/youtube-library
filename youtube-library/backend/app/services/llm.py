from typing import AsyncGenerator, Optional
import json

import httpx

from app.config import get_settings
from app.api.chat import ChatMessage

settings = get_settings()


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }


async def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    timeout: float = 120.0,
) -> str:
    """Run a chat completion against the OpenAI-compatible LLM API."""
    payload: dict = {
        "model": model or settings.llm_chat_model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.llm_api_base}/chat/completions",
            headers=_auth_headers(),
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
        return (result["choices"][0]["message"].get("content") or "").strip()


async def chat_completion_stream(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.7,
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """Stream a chat completion, yielding content deltas as they arrive."""
    payload = {
        "model": model or settings.llm_chat_model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{settings.llm_api_base}/chat/completions",
            headers=_auth_headers(),
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    content = chunk["choices"][0].get("delta", {}).get("content")
                    if content:
                        yield content
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue


def build_messages(query: str, context: str, history: list[ChatMessage]) -> list[dict]:
    """Build messages for the chat completion API."""
    from app.services.prompts import chat_system_prompt, context_label

    # Context is merged into the single leading system message — strict
    # OpenAI-compatible endpoints reject system messages after position 0.
    system_content = chat_system_prompt()
    if context:
        system_content += f"\n\n{context_label()}\n\n{context}"

    messages = [
        {"role": "system", "content": system_content}
    ]

    # Add conversation history
    for msg in history[-4:]:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })

    # Add current query
    messages.append({"role": "user", "content": query})

    return messages


async def generate_response(
    query: str,
    context: str,
    history: list[ChatMessage]
) -> str:
    """Generate a response for the RAG chat."""
    messages = build_messages(query, context, history)
    return await chat_completion(messages, temperature=0.7)


async def generate_response_stream(
    query: str,
    context: str,
    history: list[ChatMessage]
) -> AsyncGenerator[str, None]:
    """Generate a streaming response for the RAG chat."""
    messages = build_messages(query, context, history)
    async for content in chat_completion_stream(messages, temperature=0.7):
        yield content
