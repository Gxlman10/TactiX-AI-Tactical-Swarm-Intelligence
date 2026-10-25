# Infra

TactiX ships as plain Docker images (backend + frontend), so it deploys to **any container
host** — a VPS, Render, Fly.io, Railway, Cloud Run, App Runner, Azure Container Apps, etc. It
is not tied to a specific cloud, and needs neither a managed database nor a model provider to
run the demo.

- `DEPLOY.md` — the deployment runbook: images, running the containers anywhere, configuration,
  and the optional database and model provider.

The backend image is built by `.github/workflows/build-image.yml` (GitHub Actions → GHCR),
which needs no local Docker. The `Dockerfile`s live in `backend/` and `frontend/`; `compose.yaml`
at the repo root runs the backend + PostgreSQL locally.
