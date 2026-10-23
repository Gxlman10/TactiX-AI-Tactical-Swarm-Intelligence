# Infra

Azure deployment (Bicep + Azure CLI): the backend on **Azure Container Apps** (scale-to-zero
capable) with **Azure Database for PostgreSQL** Flexible Server, and the **Microsoft Foundry**
model for the live agents.

- `main.bicep` — the resource-group-scoped deployment (Log Analytics, Container Apps
  environment, backend Container App, PostgreSQL Flexible B1ms).
- `deploy.sh` — one-shot deploy: resource group → ACR → `az acr build` (no local Docker) →
  Bicep. Overridable via `TACTIX_*` env vars.
- `DEPLOY.md` — the runbook: prerequisites, cost notes, migrations, enabling Foundry, teardown.

> **Starting point, not yet validated against a live subscription.** Run `deploy.sh` once and
> iterate. See `DEPLOY.md`.
