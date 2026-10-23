#!/usr/bin/env bash
# TactiX — deploy the backend to Azure Container Apps + PostgreSQL.
#
# Prerequisites:
#   - Azure CLI installed and logged in:  az login
#   - A subscription selected:            az account set --subscription "<name-or-id>"
#   - The containerapp extension:         az extension add --name containerapp --upgrade
#
# Usage (from the repo root or anywhere):
#   TACTIX_PG_PASSWORD='<a-strong-password>' ./infra/deploy.sh
#
# Everything is overridable via the TACTIX_* environment variables below.
# NOT YET VALIDATED against a live subscription — run once and iterate. See infra/DEPLOY.md.
set -euo pipefail

RG="${TACTIX_RG:-tactix-rg}"
LOCATION="${TACTIX_LOCATION:-eastus}"
ACR="${TACTIX_ACR:-tactixacr$RANDOM}"
PREFIX="${TACTIX_PREFIX:-tactix}"
IMAGE_TAG="${TACTIX_IMAGE_TAG:-latest}"
PG_ADMIN_USER="${TACTIX_PG_USER:-tactix}"
PG_ADMIN_PASSWORD="${TACTIX_PG_PASSWORD:?Set TACTIX_PG_PASSWORD to a strong password}"
FOUNDRY_ENDPOINT="${TACTIX_FOUNDRY_ENDPOINT:-}"
FOUNDRY_MODEL="${TACTIX_FOUNDRY_MODEL:-}"
MIN_REPLICAS="${TACTIX_MIN_REPLICAS:-1}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Resource group: $RG ($LOCATION)"
az group create -n "$RG" -l "$LOCATION" -o none

echo "==> Container registry: $ACR"
az acr create -g "$RG" -n "$ACR" --sku Basic --admin-enabled true -o none
REGISTRY_SERVER="$(az acr show -g "$RG" -n "$ACR" --query loginServer -o tsv)"
REGISTRY_USER="$(az acr credential show -g "$RG" -n "$ACR" --query username -o tsv)"
REGISTRY_PASSWORD="$(az acr credential show -g "$RG" -n "$ACR" --query 'passwords[0].value' -o tsv)"

# Builds the image inside ACR, so no local Docker is required.
# To enable the live agents later, add `--extra agents` to backend/Dockerfile's `uv sync`
# and rebuild (see DEPLOY.md).
echo "==> Building backend image in ACR (no local Docker needed)"
az acr build -r "$ACR" -t "tactix-backend:$IMAGE_TAG" "$ROOT/backend" -o none

echo "==> Deploying infrastructure (Bicep)"
az deployment group create -g "$RG" \
  --template-file "$ROOT/infra/main.bicep" \
  --parameters \
    namePrefix="$PREFIX" \
    backendImage="$REGISTRY_SERVER/tactix-backend:$IMAGE_TAG" \
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
