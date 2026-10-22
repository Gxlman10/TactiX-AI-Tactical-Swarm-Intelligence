# Live match API

The FastAPI application exposes the default fictional league, temporary match
sessions, replay controls, visible events, core/advanced metrics and resumable SSE.

Run from `backend/` using the existing environment:

```powershell
uv run uvicorn tactix.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Explore `/docs` or fetch `/openapi.json`. Start a paused session with
`POST /api/v1/sessions` and `{}`, open `/api/v1/sessions/{session_id}/stream`, then
POST `{"action":"play"}` to `/api/v1/sessions/{session_id}/controls`.

The complete [frontend integration contract](../.claude/docs/ai/live-match-api/api-handoff.md)
describes payloads, cursor recovery, seek revisions, errors and operating limits.
Existing `/health` behavior is preserved. Startup generates the league once;
match generation and metric computation run outside the async request loop.

Run `uv run pytest tests/unit/test_api.py tests/unit/test_api_socket.py -q` for
focused checks, including a real loopback Uvicorn server with simultaneous SSE
readers and reconnect recovery. Use the PostgreSQL test configuration for the full
backend suite. No schema migration or dependency change is required for this task.
