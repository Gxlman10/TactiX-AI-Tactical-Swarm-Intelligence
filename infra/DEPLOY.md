# Deploying TactiX to Azure

Serverless backend on **Azure Container Apps** + **Azure Database for PostgreSQL Flexible
Server**, driven by `infra/main.bicep` and `infra/deploy.sh`.

> **Status: starting point, not yet validated against a live subscription.** Run `deploy.sh`
> once from a machine with the Azure CLI and iterate on any errors before relying on it. The
> interactive `az login` path needs no Entra app registration.

## Cost (Azure for Students, ~$100 credit)

- **Container Apps** scale-to-zero → ~$0 when idle (set `TACTIX_MIN_REPLICAS=0`). For a live
  demo, `minReplicas=1` (the default) avoids cold starts and dropped SSE connections at a
  small always-on cost.
- **PostgreSQL Flexible B1ms** is the one resource that bills while idle (~$12–15/month). For
  a demo kept up until Nov 10 that is a few dollars — but **delete the resource group when you
  are done** (see Teardown) so it stops billing.

## Prerequisites

```bash
az login
az account set --subscription "<your-subscription>"
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.DBforPostgreSQL
az provider register --namespace Microsoft.OperationalInsights
```

Some subscriptions restrict the **allowed regions** via policy. List yours and pick one that is
allowed (and set `TACTIX_LOCATION` to it):

```bash
az policy assignment list --disable-scope-strict-match \
  --query "[].parameters.listOfAllowedLocations.value" -o json
```

## The image: GitHub Actions → GHCR (no local Docker, no ACR Tasks)

Student subscriptions commonly disallow **ACR Tasks**, so `az acr build` fails. Instead, the
`.github/workflows/build-image.yml` workflow builds the backend on GitHub's runners and
publishes it to the **GitHub Container Registry**:
`ghcr.io/<owner>/tactix-backend:latest`.

1. Merge the workflow to `dev`/`main` (or run it from the Actions tab → *Build backend image*
   → *Run workflow*). Wait for it to finish green.
2. **Make the package public once** so Container Apps can pull it without credentials:
   GitHub → your profile → **Packages** → `tactix-backend` → **Package settings** → *Change
   visibility* → **Public**. (Alternatively keep it private and pass a pull PAT as the
   `registry*` parameters.)

## Deploy

Point the deploy at the public image — no ACR is created:

```bash
export TACTIX_PG_PASSWORD='<a-strong-password>'
export TACTIX_LOCATION=brazilsouth   # an allowed region
export TACTIX_BACKEND_IMAGE='ghcr.io/<owner>/tactix-backend:latest'
./infra/deploy.sh
```

`deploy.sh` creates the resource group, deploys the Bicep (Log Analytics, Container Apps
environment, the backend Container App pulling the public image, and PostgreSQL Flexible
B1ms), and prints the `backendUrl`, `postgresHost`, and `backendPrincipalId` outputs.

> Leaving `TACTIX_BACKEND_IMAGE` unset falls back to the ACR-build path, which needs ACR Tasks.

Verify:

```bash
curl "<backendUrl>/health"
```

Override any default via `TACTIX_*` env vars (`TACTIX_RG`, `TACTIX_LOCATION`,
`TACTIX_MIN_REPLICAS`, …) — see the top of `deploy.sh`.

## Database migrations

The Bicep provisions an empty PostgreSQL server. Apply the Alembic schema once, from a machine
that can reach it (the server allows Azure services; for a local run add your IP under the
server's networking, or run migrations from a container in the environment):

```bash
cd backend
TACTIX_DATABASE_URL='postgresql+psycopg://tactix:<pwd>@<postgresHost>:5432/tactix?sslmode=require' \
  uv run alembic upgrade head
```

> The live match flow builds the demo in memory per session, so the backend serves `/health`
> and the demo sessions without a populated database; migrations are needed only for the
> persistence features. If you want to skip PostgreSQL entirely for a leaner demo, remove the
> `postgres*` resources from `main.bicep` and drop `TACTIX_DATABASE_URL`.

## Enabling the live agents (Foundry)

The base image installs without the preview `agents` extra, so the backend runs but
`/analyze` returns 503 until Foundry is configured. To enable the swarm live:

1. Create a **Microsoft Foundry** project and deploy a model; note the project endpoint and
   the deployment name.
2. Grant the Container App's **managed identity** (the `backendPrincipalId` output) access to
   the Foundry project (e.g. the `Azure AI Developer` role on the project), so
   `TACTIX_FOUNDRY_AUTHENTICATION=managed_identity` can authenticate without a key.
3. Add `--extra agents` to `backend/Dockerfile`'s `uv sync` line, then redeploy with
   `TACTIX_FOUNDRY_ENDPOINT` and `TACTIX_FOUNDRY_MODEL` set.

Foundry/Azure OpenAI access and model quota may need to be requested on a student
subscription — check early.

## Teardown

```bash
az group delete -n tactix-rg --yes --no-wait
```

## Follow-ups (not in this starting point)

- Frontend build is broken in a clean environment; dockerizing/serving it comes after that fix.
- CI/CD deploy (GitHub Actions) via OIDC needs an Entra app registration, which the university
  tenant may restrict — this manual `az` path avoids that.
