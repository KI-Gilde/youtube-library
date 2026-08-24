---
description: Install and start YouTube Library on this machine, verifying each step
---

Install YouTube Library on this machine by following @docs/INSTALL.md. Work through it as an operator, not a narrator — run the commands, read the output, and only claim a step done when its verification passed.

Steps:

1. **Prerequisites** — verify `docker compose version` and `python3 --version` (3.10+). If Docker is missing, stop and tell the user how to install it for their OS; do not attempt to install Docker yourself.
2. **LLM endpoint** — ask the user which OpenAI-compatible endpoint to use (base URL ending in `/v1`, API key, chat model, utility model, embedding model). Remind them the embedding model must produce 1024-dimensional vectors (`bge-m3` is the tested default). If they have no endpoint yet, present the options from the guide (hosted provider, Ollama, bundled llama.cpp chat-only) and help set one up.
3. **Configure** — create `youtube-library/.env` from `.env.example` with their values and a fresh `POSTGRES_PASSWORD`. Never print the API key back into the conversation.
4. **Test the endpoint** — run the two curl checks (chat completion and embeddings) from the guide before starting anything. On failure, fix base URL/key/model names first; do not continue with a broken endpoint.
5. **Start** — run `./start.sh` from `youtube-library/`. The first build takes several minutes; wait for it rather than assuming success.
6. **Verify** — `curl http://localhost:9071/health` must return `{"status":"healthy"}`, `docker compose ps` must show postgres, qdrant, backend, and frontend running, and the backend log should contain "Scheduler started". If a port is taken, consult the troubleshooting table in the guide.
7. **Hand over** — tell the user the app is at http://localhost:9070 and that they should import a first channel via the Import tab, then check back once videos reach "done" to try the chat.

If anything fails, use the troubleshooting section of @docs/INSTALL.md before improvising.
