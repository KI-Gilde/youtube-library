# YouTube Library

A self-hosted YouTube channel library with automatic transcription and RAG-powered chat.

Import a YouTube channel and the app downloads every video, transcribes it with Whisper, cleans up the transcript with an LLM, generates summaries, and indexes everything in a vector database. You can then browse your library, watch videos locally, search transcripts semantically, and chat with an assistant that recommends videos from the library based on their actual content.

**Demo videos:** 🎬 [Product tour (English)](docs/media/yt-library-promo-en.mp4) · [Produkt-Tour (Deutsch)](docs/media/yt-library-promo-de.mp4)

## Features

- **Channel import** — add a channel URL, all videos are discovered and queued automatically; a scheduler checks for new uploads periodically
- **Processing pipeline** — download (yt-dlp) → transcribe (faster-whisper) → refine transcript (LLM) → summarize (LLM) → embed (vector index), with status tracking per video
- **Library UI** — browse videos with thumbnails, summaries, and full transcripts; stream downloaded videos in the browser
- **Semantic search** — find videos by meaning, not just keywords, via transcript chunk embeddings in Qdrant
- **RAG chat** — a streaming chat assistant that answers questions and pitches the videos from your library that cover the topic

## Architecture

| Service    | Tech                                  | Port (host) |
|------------|---------------------------------------|-------------|
| Frontend   | React 18 + TypeScript + Vite + Tailwind | 9070      |
| Backend    | FastAPI + SQLAlchemy + APScheduler    | 9071        |
| PostgreSQL | postgres:16                           | 9072        |
| Qdrant     | qdrant/qdrant                         | 9073        |
| LLM server | llama.cpp (optional, `--profile llm`) | 9075        |

Transcription runs locally via faster-whisper. Chat, transcript refinement, summaries, and embeddings go through an **OpenAI-compatible API** that you configure — a hosted provider or your own server. The endpoint must offer chat completions and embeddings (default embedding model: `bge-m3`, 1024 dimensions).

## Getting started

Requirements: Docker (with Compose), Python 3.10+.

For a detailed walkthrough — including LLM endpoint options and troubleshooting — see **[docs/INSTALL.md](docs/INSTALL.md)**. If you use [Claude Code](https://claude.com/claude-code), you can also just run `/install` in the repository root and let it set everything up for you.

```bash
cd youtube-library
cp .env.example .env    # then set LLM_API_BASE, LLM_API_KEY, and model names
./start.sh              # downloads the Whisper model, builds and starts all services
```

Then open http://localhost:9070, go to **Import**, and paste a channel URL (e.g. `https://www.youtube.com/@ChannelName`).

- API docs: http://localhost:9071/docs
- Qdrant dashboard: http://localhost:9073/dashboard
- Logs: `docker compose logs -f backend`
- Stop: `docker compose down`
- Full reset (deletes all downloaded data and volumes): `./reset.sh`

### Configuration

All settings live in `youtube-library/.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_BASE` | local llama-server | Base URL of an OpenAI-compatible API (`.../v1`) |
| `LLM_API_KEY` | `sk-no-key-required` | API key for that endpoint |
| `LLM_CHAT_MODEL` | `gpt-oss-20b` | Model used for RAG chat answers |
| `LLM_UTILITY_MODEL` | `gpt-oss-20b` | Faster model for transcript refinement and summaries |
| `EMBEDDING_MODEL` | `bge-m3` | Embedding model served by the same API |
| `WHISPER_MODEL` | `medium` | Local Whisper size: tiny, base, small, medium, large |
| `LANGUAGE` | `de` | App language (`de` or `en`) for the web UI and all LLM output — summaries, transcript refinement, chat answers. Rebuild after changing. |
| `POSTGRES_*` | see example | Database credentials |

Without an external API you can start the bundled llama.cpp server (`docker compose --profile llm up -d`, place a GGUF file in `youtube-library/models/`), but note it serves chat only — embeddings still need an endpoint that provides them.

## Development

```bash
# Frontend
cd youtube-library/frontend
npm install
npm run dev      # http://localhost:5173
npm run build
npm run lint

# Backend (runs against the dockerized Postgres/Qdrant)
cd youtube-library/backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Project structure

```
youtube-library/
├── backend/app/
│   ├── api/          # REST + SSE endpoints (channels, videos, chat)
│   ├── models/       # SQLAlchemy models (Channel, Video + status enum)
│   ├── scheduler/    # periodic new-video checks
│   └── services/     # pipeline steps: youtube, transcription, refinement,
│                     # summary, embedding, rag, llm
├── frontend/src/     # React app (Library, Import, Chat)
├── llama-server/     # optional local llama.cpp server image
└── docker-compose.yml
```

## Legal note

This tool downloads content from YouTube for personal, local use. You are responsible for ensuring that your use complies with YouTube's Terms of Service and the copyright laws of your jurisdiction.

## License

[MIT](LICENSE)
