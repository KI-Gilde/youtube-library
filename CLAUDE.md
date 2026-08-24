# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Self-hosted YouTube channel library: a full-stack web application (FastAPI + React) in `youtube-library/` that imports YouTube channels, downloads and transcribes all videos, and offers semantic search plus RAG-based chat over the transcripts.

## Commands

```bash
cd youtube-library

# Start all services (PostgreSQL, Qdrant, Backend, Frontend)
./start.sh
# Or manually:
docker compose up --build -d

# Start with the optional local llama.cpp server
docker compose --profile llm up --build -d

# View logs
docker compose logs -f backend

# Stop services
docker compose down

# Delete all downloaded data and Docker volumes
./reset.sh
```

**Service Ports:**
- Frontend: http://localhost:9070
- Backend API: http://localhost:9071
- API Docs: http://localhost:9071/docs
- Qdrant Dashboard: http://localhost:9073/dashboard
- PostgreSQL: localhost:9072
- LLM Server (if enabled): http://localhost:9075

### Frontend Development

```bash
cd youtube-library/frontend
npm install
npm run dev      # Dev server at http://localhost:5173
npm run build    # Production build
npm run lint     # Run ESLint
```

## Architecture

### Processing Pipeline

Videos are processed through a multi-step pipeline (`backend/app/services/pipeline.py`), one video at a time (guarded by an asyncio lock):

1. **Download** (`youtube.py`) - Uses yt-dlp to download video and thumbnail
2. **Transcribe** (`transcription.py`) - Uses faster-whisper for local speech-to-text
3. **Refine** (`refinement.py`) - Uses the LLM API to fix transcription errors
4. **Summarize** (`summary.py`) - Generates a short summary via the LLM API
5. **Embed** (`embedding.py`) - Gets embeddings from the LLM API, stores chunks in Qdrant

### LLM Integration

All LLM and embedding calls go through a single OpenAI-compatible endpoint (`services/llm.py`, configured via `LLM_API_BASE`/`LLM_API_KEY`):

- **Chat (RAG)**: `LLM_CHAT_MODEL`, streamed via SSE (`/api/chat/stream`); the SSE parser reads only `delta.content` and ignores `reasoning_content`
- **Refinement & Summary**: `LLM_UTILITY_MODEL` via the shared helper `llm.chat_completion()`
- **Embeddings**: `EMBEDDING_MODEL` (default `bge-m3`, 1024 dimensions) via `/v1/embeddings`

Only Whisper runs locally. The `llama-server` docker-compose profile provides an optional local chat endpoint (no embeddings).

### RAG Chat System

- **Vector DB**: Qdrant for semantic search over transcript chunks (`services/embedding.py`, `services/rag.py`)
- **API**: Streaming SSE responses via `/api/chat/stream` (`api/chat.py`)

### Database Models

- **Channel**: YouTube channels being monitored (`models/channel.py`)
- **Video**: Individual videos with status tracking through pipeline stages (`models/video.py`)
- **VideoStatus**: PENDING -> DOWNLOADING -> TRANSCRIBING -> REFINING -> SUMMARIZING -> EMBEDDING -> DONE | ERROR

On backend startup, videos stuck in a processing state are reset to PENDING (`main.py`).

### Key Configuration

Settings are managed via `backend/app/config.py` (pydantic-settings) and environment variables; docker-compose reads `.env` for substitution. See `.env.example` for the full list (`LLM_API_BASE`, `LLM_API_KEY`, `LLM_CHAT_MODEL`, `LLM_UTILITY_MODEL`, `EMBEDDING_MODEL`, `WHISPER_MODEL`, `POSTGRES_*`).

## Dependencies

### Backend
- FastAPI + SQLAlchemy + PostgreSQL
- yt-dlp (YouTube downloading)
- faster-whisper (transcription)
- httpx (LLM API client)
- qdrant-client (vector database)
- APScheduler (background jobs)

### Frontend
- React 18 + TypeScript + Vite
- TanStack Query (data fetching)
- Tailwind CSS + lucide-react (styling/icons)
