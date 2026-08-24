# Design: Responsives UI & geschmeidige Hintergrund-Pipeline

Datum: 2026-08-10
Scope: `youtube-library` (FastAPI-Backend + React-Frontend)

## Ziel

1. Die Web-App soll auf allen Bildschirmgrößen benutzbar sein (responsive Design).
2. Die Video-Pipeline soll zuverlässig und ohne manuelles Zutun im Hintergrund laufen,
   ohne sich selbst zu sabotieren, und die UI soll ihren Fortschritt flüssig anzeigen.

## Befunde

### Backend

| # | Problem | Datei |
|---|---------|-------|
| 1 | `reset_stuck_videos` (Scheduler) resettet DOWNLOADING-Videos anhand `created_at` und bricht dadurch laufende Downloads älterer Videos ab | `scheduler/jobs.py` |
| 2 | `/videos/{id}/reprocess` umgeht den Verarbeitungs-Lock (`process_video` direkt) → parallele Pipelines | `api/videos.py` |
| 3 | Neue Videos warten bis zu 5 min auf den Scheduler statt sofort verarbeitet zu werden | `services/youtube.py` |
| 4 | Qdrant-IDs via `hash()` sind nicht prozessstabil → Duplikate bei Re-Embedding; alte Chunks werden nie gelöscht | `services/embedding.py` |
| 5 | Startup-Reset deckt REFINING/SUMMARIZING nicht ab | `main.py` |

### Frontend

| # | Problem | Datei |
|---|---------|-------|
| 6 | Desktop-only-Layout: feste `w-72`-Sidebar, starre `grid-cols-3`/`grid-cols-4`, Modal `w-[420px]` | `App.tsx`, `Import.tsx` |
| 7 | Chat nutzt blockierenden `/chat`-Endpoint statt vorhandenem SSE-Stream | `Chat.tsx`, `client.ts` |
| 8 | Status-Polling starr 2 s (auch idle); Stats/Videos refetchen nicht, wenn der Scheduler im Hintergrund startet | `Import.tsx` |

## Entscheidungen

- **Kein Task-Queue-Umbau (Celery/arq):** Die App ist Single-Instance; der bestehende
  asyncio-Lock + Scheduler reicht, wenn alle Wege durch den Lock führen. YAGNI.
- **Polling statt SSE für Verarbeitungsstatus:** adaptives Polling (2 s aktiv / 8 s idle)
  erreicht fast dieselbe Gefühls-Latenz mit minimaler Komplexität. Der Chat bekommt
  dagegen echtes Streaming, weil der Endpoint schon existiert.
- **Sidebar → Topbar auf Mobil:** unter `lg` wird die Sidebar zu einer kompakten
  Kopfleiste mit horizontaler Navigation; kein Drawer nötig.

## Maßnahmen

### Hintergrundprozesse

1. `scheduler/jobs.py`: `reset_stuck_videos` resettet nur noch, wenn die Pipeline
   nachweislich nicht läuft (`is_processing()`), und deckt alle Zwischenstatus ab.
   Kein `created_at`-Kriterium mehr.
2. `api/videos.py` (`/reprocess`): Video auf PENDING setzen, dann
   `process_pending_videos` als Background-Task (respektiert den Lock).
   `pipeline.reprocess_failed_videos` läuft ebenfalls über den Lock-Pfad.
3. `services/youtube.py`: Nach dem Import neuer Videos wird die Verarbeitung sofort
   per `asyncio.create_task(process_pending_videos(...))` angestoßen (Lock verhindert
   Doppelläufe); der 5-min-Scheduler bleibt als Fallback.
4. `services/embedding.py`: deterministische Punkt-IDs via `uuid5(youtube_id_chunkindex)`;
   vor dem Upsert werden alte Punkte des Videos per Filter gelöscht.
5. `main.py`: Startup-Reset deckt alle In-Progress-Status ab.

### Responsiveness

6. `App.tsx`: `lg:`-Sidebar + mobile Topbar mit Icon-Navigation; Layout `flex-col lg:flex-row`.
7. `Import.tsx`/`Library.tsx`/`Chat.tsx`: Paddings `p-4 md:p-8`, Stats
   `grid-cols-2 lg:grid-cols-4`, Hauptgrid `grid-cols-1 lg:grid-cols-3`, Such-/Filterzeile
   stapelbar, Modal `w-full max-w-md mx-4`, Header umbruchfähig.
8. `Chat.tsx` + `client.ts`: SSE-Streaming über `/api/chat/stream` (fetch + ReadableStream),
   Tokens erscheinen live; Quellen kommen als erstes Event.
9. `Import.tsx`: adaptives Polling — `processingStatus` 2 s aktiv / 8 s idle; Videos & Stats
   refetchen alle 3 s, solange `is_processing` gemeldet wird.

## Fehlerbehandlung

- Streaming-Chat: bei Netz-/Parsefehler wird die bisherige Teilantwort behalten und eine
  Fehlermeldung angehängt; Abbruch über `AbortController` beim Unmount.
- Auto-Trigger im Import ist fire-and-forget mit try/except-Logging — ein Fehler im
  Pipeline-Start darf den Kanal-Import nicht scheitern lassen.

## Nachtrag (gleicher Tag): zentraler LLM-Endpoint

Alle LLM- und Embedding-Aufrufe laufen jetzt über einen zentralen OpenAI-kompatiblen
Endpoint (konfiguriert in `app/config.py`, überschreibbar per env):

- **Chat (RAG):** `qwen3.6-35b` (Reasoning-Modell; der SSE-Parser wertet nur
  `delta.content` aus und ignoriert `reasoning_content`).
- **Refinement & Summary:** `qwen3.6-35b-fast` über den gemeinsamen Helfer
  `llm.chat_completion()`; ersetzt lokales Ollama (`host.docker.internal`) und den
  llama.cpp-Server.
- **Embeddings:** `bge-m3` über `/v1/embeddings` (1024 Dimensionen — identisch zur
  bestehenden Qdrant-Collection, Bestandsindex bleibt gültig). Das lokale
  FlagEmbedding-Modell entfällt komplett (schnellerer Start, weniger CPU,
  kleineres Docker-Image; `sentence-transformers`/`FlagEmbedding` aus den
  Requirements entfernt).

Der optionale `llama-server`-Service in docker-compose (Profil `llm`) wird nicht
mehr benötigt, bleibt aber vorerst stehen.

## Verifikation

- Backend: `python -m py_compile` über alle geänderten Module.
- Frontend: `npm run build` und `npm run lint` müssen sauber durchlaufen.
- Endpoint live getestet: Chat (non-streaming + SSE-Streaming), Embeddings
  (Batch, Dimension 1024), Summary-Verhalten des Fast-Modells bei `max_tokens=256`.
