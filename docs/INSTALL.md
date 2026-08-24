# Installation Guide

Step-by-step instructions for installing YouTube Library on a fresh machine.

> **Using Claude Code?** Open a terminal in the repository root, start `claude`, and run `/install` — Claude will walk through this guide for you, ask for your LLM endpoint, and verify each step.

## 1. Prerequisites

| Requirement | Notes |
|-------------|-------|
| Docker with Compose v2 | `docker compose version` must work (Docker Desktop on macOS/Windows, Docker Engine + compose plugin on Linux) |
| Python 3.10+ | Only used by `start.sh` to pre-download the Whisper model |
| Git | To clone the repository |
| Disk space | ~2 GB for images and the Whisper model, plus room for downloaded videos (budget several GB per channel) |
| LLM endpoint | Any OpenAI-compatible API providing **chat completions and embeddings** (see step 3) |

Verify:

```bash
docker compose version
python3 --version
```

## 2. Clone the repository

```bash
git clone <repository-url>
cd <repository-name>/youtube-library
```

## 3. Choose an LLM backend

All chat, transcript refinement, summaries, and embeddings go through one OpenAI-compatible API. Pick one option:

**Option A — Hosted provider.** Any service exposing an OpenAI-compatible `/v1` API with a chat model and an embedding model.

**Option B — Self-hosted server.** For example [Ollama](https://ollama.com) (with `bge-m3` pulled for embeddings and any chat model, base URL `http://host.docker.internal:11434/v1` when the backend runs in Docker on the same machine), vLLM, LiteLLM, or llama.cpp with embeddings enabled.

**Option C — Bundled llama.cpp server (chat only).** `docker compose --profile llm up -d` starts a llama.cpp server on port 9075 using a GGUF file from `./models/`. It does **not** serve embeddings, so you still need an embedding-capable endpoint for the pipeline to complete.

> **Embedding constraint:** the Qdrant collection is created with **1024-dimensional** vectors. Use an embedding model that outputs 1024 dimensions — the default `bge-m3` does. Other dimensions will cause the embed step to fail.

## 4. Configure

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```ini
LLM_API_BASE=https://your-endpoint.example.com/v1
LLM_API_KEY=sk-your-key
LLM_CHAT_MODEL=your-chat-model
LLM_UTILITY_MODEL=your-fast-model   # may be the same as LLM_CHAT_MODEL
EMBEDDING_MODEL=bge-m3
POSTGRES_PASSWORD=pick_something
```

Optional: `WHISPER_MODEL` (tiny/base/small/medium/large — larger is more accurate and slower; default `medium`).

Test your endpoint before starting (both must return valid JSON, not errors):

```bash
curl -s "$LLM_API_BASE/chat/completions" -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"your-chat-model","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'

curl -s "$LLM_API_BASE/embeddings" -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"bge-m3","input":["ping"]}'
```

## 5. Start

```bash
./start.sh
```

This creates the data directories, downloads the Whisper model into a local virtualenv cache, then runs `docker compose up --build -d`. The first build takes several minutes.

Manual alternative: `docker compose up --build -d` (the Whisper model is then downloaded on first transcription instead).

## 6. Verify

```bash
curl -s http://localhost:9071/health        # -> {"status":"healthy"}
docker compose ps                           # postgres, qdrant, backend, frontend running
docker compose logs backend | tail -20      # "Scheduler started." / "Embedding backend ready."
```

Then open:

- Frontend: http://localhost:9070
- API docs: http://localhost:9071/docs
- Qdrant dashboard: http://localhost:9073/dashboard

## 7. First import

1. Open http://localhost:9070 and go to **Import**.
2. Paste a channel URL, e.g. `https://www.youtube.com/@ChannelName`.
3. Videos are discovered and processed one at a time (download → transcribe → refine → summarize → embed). Watch progress in the Library view or with `docker compose logs -f backend`.
4. Once the first videos reach **done**, try the **Chat** tab.

A scheduler re-checks imported channels for new uploads every hour.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Port already in use | The stack uses host ports 9070–9075. Stop the conflicting service or change the mappings in `docker-compose.yml`. |
| `401`/`404` errors in backend logs during refine/embed | `LLM_API_BASE` (must end in `/v1`), `LLM_API_KEY`, or model names are wrong — re-run the curl tests from step 4, then `docker compose up -d` to reload env. |
| Embed step fails with a vector size error | Your embedding model does not output 1024 dimensions. Switch to `bge-m3` (or recreate the Qdrant collection to match). |
| Transcription is very slow | Use a smaller `WHISPER_MODEL` (e.g. `small`) — transcription runs on CPU inside the container. |
| Videos stuck in a processing state after a crash | Restart the backend (`docker compose restart backend`) — stuck videos are reset to pending on startup. |
| Start over completely | `./reset.sh` deletes all downloaded data and Docker volumes (asks for confirmation). |

## Updating

```bash
git pull
cd youtube-library
docker compose up --build -d
```

Database and vector index live in Docker volumes and survive rebuilds.
