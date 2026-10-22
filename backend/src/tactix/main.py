"""FastAPI application entrypoint. Routers are mounted here as each layer lands."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from tactix import __version__
from tactix.api.routes import router
from tactix.api.sessions import SessionStore
from tactix.config import settings
from tactix.universe.generator import generate_league


@asynccontextmanager
async def lifespan(application: FastAPI):
    league = await run_in_threadpool(generate_league)
    application.state.sessions = SessionStore(league)
    try:
        yield
    finally:
        application.state.sessions.close()


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
app.include_router(router)

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
