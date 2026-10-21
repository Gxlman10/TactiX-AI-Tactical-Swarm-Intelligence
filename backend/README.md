# TactiX backend

Python + FastAPI. Layers: `universe/` and `simulation/` (synthetic data), `metrics/`
(deterministic stats), `agents/` + `workflows/` (the swarm on Microsoft Agent Framework),
`persistence/` (PostgreSQL) and `api/` (REST + SSE). Shared contracts live in `domain/`.

## Local setup

```bash
uv sync                 # base env (Python 3.12, pinned via .python-version)
uv sync --extra agents  # add Microsoft Agent Framework + Foundry when you work on Layer 3
uv run uvicorn tactix.main:app --reload
uv run pytest
uv run ruff check .
```

The database defaults to the local PostgreSQL from the repo-root `compose.yaml`
(`docker compose up -d db`). Configuration is read from `../.env` (see `../.env.example`).
