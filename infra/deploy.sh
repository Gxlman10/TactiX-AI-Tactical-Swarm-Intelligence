#!/usr/bin/env bash
# TactiX — deploy the backend to Azure Container Apps + PostgreSQL.
#
# Two image paths:
#   1. Prebuilt public image (recommended; no local Docker, no ACR Tasks). Set
#      TACTIX_BACKEND_IMAGE to a public image, e.g. the one the GitHub Actions workflow
#      pushes to GHCR:  ghcr.io/<owner>/tactix-backend:latest
#   2. ACR build (needs ACR Tasks, which some subscriptions — e.g. Azure for Students —
#      disallow). Used when TACTIX_BACKEND_IMAGE is unset.
#
# Prerequisites:
#   - Azure CLI installed and logged in:  az login
#   - A subscription selected:            az account set --subscription "<name-or-id>"
#   - The containerapp extension:         az extension add --name containerapp --upgrade
#
# Usage (prebuilt image):
#   TACTIX_PG_PASSWORD='<strong>' TACTIX_LOCATION=brazilsouth \
#     TACTIX_BACKEND_IMAGE='ghcr.io/<owner>/tactix-backend:latest' ./infra/deploy.sh
#
# Everything is overridable via the TACTIX_* environment variables below.
set -euo pipefail

RG="${TACTIX_RG:-tactix-rg}"
LOCATION="${TACTIX_LOCATION:-eastus}"
ACR="${TACTIX_ACR:-tactixacr$RANDOM}"
PREFIX="${TACTIX_PREFIX:-tactix}"
IMAGE_TAG="${TACTIX_IMAGE_TAG:-latest}"
BACKEND_IMAGE_OVERRIDE="${TACTIX_BACKEND_IMAGE:-}"
PG_ADMIN_USER="${TACTIX_PG_USER:-tactix}"
PG_ADMIN_PASSWORD="${TACTIX_PG_PASSWORD:?Set TACTIX_PG_PASSWORD to a strong password}"
FOUNDRY_ENDPOINT="${TACTIX_FOUNDRY_ENDPOINT:-}"
FOUNDRY_MODEL="${TACTIX_FOUNDRY_MODEL:-}"
MIN_REPLICAS="${TACTIX_MIN_REPLICAS:-1}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Resource group: $RG ($LOCATION)"
az group create -n "$RG" -l "$LOCATION" -o none

# The registry params stay empty for a public image, so the Container App pulls without creds.
REGISTRY_SERVER=""
REGISTRY_USER=""
REGISTRY_PASSWORD=""

if [ -n "$BACKEND_IMAGE_OVERRIDE" ]; then
  echo "==> Using prebuilt public image: $BACKEND_IMAGE_OVERRIDE (no ACR, no local Docker)"
  BACKEND_IMAGE="$BACKEND_IMAGE_OVERRIDE"
else
  echo "==> Container registry: $ACR"
  az acr create -g "$RG" -n "$ACR" --sku Basic --admin-enabled true -o none
  REGISTRY_SERVER="$(az acr show -g "$RG" -n "$ACR" --query loginServer -o tsv)"
  REGISTRY_USER="$(az acr credential show -g "$RG" -n "$ACR" --query username -o tsv)"
  REGISTRY_PASSWORD="$(az acr credential show -g "$RG" -n "$ACR" --query 'passwords[0].value' -o tsv)"
  echo "==> Building backend image in ACR (needs ACR Tasks)"
  az acr build -r "$ACR" -t "tactix-backend:$IMAGE_TAG" "$ROOT/backend" -o none
  BACKEND_IMAGE="$REGISTRY_SERVER/tactix-backend:$IMAGE_TAG"
fi

echo "==> Deploying infrastructure (Bicep)"
az deployment group create -g "$RG" \
  --template-file "$ROOT/infra/main.bicep" \
  --parameters \
    namePrefix="$PREFIX" \
    backendImage="$BACKEND_IMAGE" \
    registryServer="$REGISTRY_SERVER" \
    registryUsername="$REGISTRY_USER" \
    registryPassword="$REGISTRY_PASSWORD" \
    postgresAdminUser="$PG_ADMIN_USER" \
    postgresAdminPassword="$PG_ADMIN_PASSWORD" \
    foundryEndpoint="$FOUNDRY_ENDPOINT" \
    foundryModel="$FOUNDRY_MODEL" \
    minReplicas="$MIN_REPLICAS" \
  --query properties.outputs -o json

echo ""
echo "==> Done. The backend URL is the 'backendUrl' output above."
echo "    Health check:  curl \$(…backendUrl…)/health"
echo "    Tear down when finished:  az group delete -n $RG --yes --no-wait"
