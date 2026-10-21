"""FastAPI application entrypoint. Routers are mounted here as each layer lands."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tactix import __version__
from tactix.config import settings

app = FastAPI(title=settings.app_name, version=__version__)

# Permissive during development; tightened for the Azure deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe used by local dev and Azure Container Apps."""
    return {"status": "ok", "app": settings.app_name, "version": __version__}
