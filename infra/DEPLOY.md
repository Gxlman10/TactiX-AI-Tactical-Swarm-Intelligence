# Deploying TactiX

TactiX is a containerized app: a **backend** image (FastAPI) and a **frontend** image (the
built Vite SPA). Both are plain Docker images, so they run on **any container host** — a VPS
with Docker, Render, Fly.io, Railway, Google Cloud Run, AWS App Runner, Azure Container Apps,
etc. Nothing here is tied to a specific cloud.

> No managed database or model provider is required to run the demo. The live match flow
> builds the synthetic match in memory, so the backend serves `/health` and demo sessions
> without PostgreSQL. A database and a model provider are optional (see below).

## The images

The backend image is built and published to the GitHub Container Registry (GHCR) by
`.github/workflows/build-image.yml` on every push — `ghcr.io/<owner>/tactix-backend:latest`.
Make that GHCR package **public** once so any host can pull it without credentials.

You can also build locally:

```bash
# backend
docker build -t tactix-backend ./backend
# frontend (bake the public backend origin at build time)
docker build --build-arg VITE_API_BASE=https://your-backend.example.com -t tactix-frontend ./frontend
```

## Run

Locally with Docker Compose (backend + PostgreSQL) from the repo root:

```bash
docker compose up --build
```

On any host, run the backend container exposing port 8000 and the frontend container exposing
port 80:

```bash
docker run -d -p 8000:8000 ghcr.io/<owner>/tactix-backend:latest
docker run -d -p 80:80 tactix-frontend
```

Point the frontend at the backend with the build-time `VITE_API_BASE`, and allow its origin on
the backend with `TACTIX_CORS_ORIGINS=https://your-frontend.example.com` (comma-separated for
several). Verify with `curl https://your-backend.example.com/health`.

## Configuration (all optional)

| Variable | Purpose | Default |
|---|---|---|
| `TACTIX_DATABASE_URL` | PostgreSQL for the persistence features | local `compose.yaml` DB |
| `TACTIX_CORS_ORIGINS` | Allowed frontend origins (comma-separated) | — |
| `TACTIX_FOUNDRY_ENDPOINT` / `TACTIX_FOUNDRY_MODEL` | Live LLM agents via the optional model-provider adapter | unset → `/analyze` returns 503 |

The backend runs fully without a database or a model provider; those only enable the
persistence features and the live agents respectively. The live-agents extra is installed with
`uv sync --extra agents` and is optional — see `backend/FOUNDRY.md` for one provider adapter.

## Database (optional)

If you enable PostgreSQL, apply the schema once from a machine that can reach it:

```bash
cd backend
TACTIX_DATABASE_URL='postgresql+psycopg://user:pwd@host:5432/tactix?sslmode=require' \
  uv run alembic upgrade head
```

To run without a database, leave `TACTIX_DATABASE_URL` unset — the demo flow does not need it.
