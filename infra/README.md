# Infra

Azure deployment (Bicep + Azure CLI): the backend on **Azure Container Apps** (scale-to-zero
capable) with **Azure Database for PostgreSQL** Flexible Server, and the **Microsoft Foundry**
model for the live agents.

- `main.bicep` — the resource-group-scoped deployment (Log Analytics, Container Apps
  environment, backend Container App, PostgreSQL Flexible B1ms). The registry is optional, so
  it can pull a public image with no credentials.
- `deploy.sh` — one-shot deploy. With `TACTIX_BACKEND_IMAGE` set to a public image it just
  deploys the Bicep (no Docker, no ACR); otherwise it falls back to an `az acr build`.
- `DEPLOY.md` — the runbook: prerequisites, the GHCR image flow, cost notes, migrations,
  enabling Foundry, teardown.

The backend image is built by `.github/workflows/build-image.yml` (GitHub Actions → GHCR),
which needs no local Docker and no ACR Tasks — the path that works on Azure for Students.

> **Starting point, not yet validated against a live subscription.** Run `deploy.sh` once and
> iterate. See `DEPLOY.md`.
