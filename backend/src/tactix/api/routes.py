"""Versioned REST controls and SSE delivery for synthetic match sessions."""

from bisect import bisect_right
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from tactix.api.sessions import CreateSession, SessionInfo, SessionStore
from tactix.domain.metrics import MetricsSnapshot
from tactix.domain.universe import League
from tactix.simulation.replay import ReplayEvent, ReplayUpdate

router = APIRouter(prefix="/api/v1", tags=["match sessions"])


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PlayPause(Control):
    action: Literal["play", "pause"]


class Seek(Control):
    action: Literal["seek"]
    second: float = Field(ge=0, allow_inf_nan=False)


class Speed(Control):
    action: Literal["speed"]
    speed: float = Field(gt=0, le=10000, allow_inf_nan=False)


class EventPage(BaseModel):
    revision: int
    position_seconds: float
    events: list[ReplayEvent]
    next_sequence: int
    has_more: bool


class MetricsResponse(BaseModel):
    metrics_version: Literal["core-v1", "advanced-v1"]
    at_second: int
    revision: int
    snapshot: MetricsSnapshot


def store(request: Request) -> SessionStore:
    return request.app.state.sessions


@router.get("/league", response_model=League)
async def league(request: Request):
    return store(request).league


@router.post("/sessions", response_model=SessionInfo, status_code=201)
async def create_session(request: Request, config: CreateSession, response: Response):
    registry = store(request)
    home, away = registry.club(config.home), registry.club(config.away)
    if home.id == away.id:
        raise HTTPException(422, "Choose two distinct clubs")
    registry.reserve()
    try:
        session = await run_in_threadpool(registry.build, home, away, config)
        registry.sessions[session.id] = session
    finally:
        registry.pending -= 1
    response.headers["Location"] = f"/api/v1/sessions/{session.id}"
    return session.info()


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(request: Request):
    return [s.info() for s in store(request).sessions.values()]


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def session_info(request: Request, session_id: str):
    return store(request).get(session_id).info()


@router.post("/sessions/{session_id}/controls", response_model=ReplayUpdate)
async def control_session(
    request: Request,
    session_id: str,
    control: Annotated[PlayPause | Seek | Speed, Body(discriminator="action")],
):
    session = store(request).get(session_id)
    if isinstance(control, Seek):
        if control.second > session.player.duration:
            raise HTTPException(422, "Seek second exceeds match duration")
        session.seek(control.second)
    elif isinstance(control, Speed):
        session.player.set_speed(control.speed)
    elif control.action == "play":
        session.player.play()
    else:
        session.player.pause()
    session.notify()
    return session.player.snapshot()


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(request: Request, session_id: str):
    registry = store(request)
    session = registry.get(session_id)
    session.close()
    del registry.sessions[session_id]
    return Response(status_code=204)


@router.get("/sessions/{session_id}/events", response_model=EventPage)
async def events(
    request: Request,
    session_id: str,
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    revision: Annotated[int | None, Query(ge=0)] = None,
):
    session = store(request).get(session_id)
    state = session.player.snapshot()
    if revision is not None and revision != state.revision:
        raise HTTPException(409, "Timeline revision changed; rebuild the visible history")
    end = bisect_right(session.times, state.position_seconds)
    if after_sequence > end:
        raise HTTPException(409, "Event cursor is ahead of the visible timeline")
    stop = min(end, after_sequence + limit)
    return EventPage(
        revision=state.revision,
        position_seconds=state.position_seconds,
        events=[
            ReplayEvent(sequence=i + 1, event=session.events[i])
            for i in range(after_sequence, stop)
        ],
        next_sequence=stop + 1,
        has_more=stop < end,
    )


@router.get("/sessions/{session_id}/metrics", response_model=MetricsResponse)
async def metrics(
    request: Request,
    session_id: str,
    advanced: bool = False,
    at_second: Annotated[int | None, Query(ge=0)] = None,
):
    session = store(request).get(session_id)
    state = session.player.snapshot()
    cutoff = int(state.position_seconds) if at_second is None else at_second
    if cutoff > int(state.position_seconds):
        raise HTTPException(422, "Metrics cutoff cannot exceed the current match clock")
    if advanced:
        snapshot = await run_in_threadpool(session.metrics.snapshot, cutoff)
    else:
        # Explicit base implementation preserves the core-v1 output contract.
        from tactix.metrics.core import CoreMetrics

        snapshot = await run_in_threadpool(CoreMetrics.snapshot, session.metrics, cutoff)
    if session.closed:
        raise HTTPException(404, "Unknown or expired session")
    if session.player.snapshot().revision != state.revision:
        raise HTTPException(
            409, "Timeline changed while computing metrics; retry at the new revision"
        )
    return MetricsResponse(
        metrics_version="advanced-v1" if advanced else "core-v1",
        at_second=cutoff,
        revision=state.revision,
        snapshot=snapshot,
    )


@router.get(
    "/sessions/{session_id}/stream",
    response_class=EventSourceResponse,
    responses={
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
        400: {"description": "Invalid resume token"},
        409: {"description": "Stale or future cursor"},
        429: {"description": "Subscriber limit"},
    },
)
async def stream(
    request: Request,
    session_id: str,
    last_event_id: Annotated[str | None, Header(max_length=150)] = None,
):
    registry = store(request)
    session = registry.get(session_id)
    revision, cursor = session.resume_cursor(last_event_id)
    if session.subscribers >= registry.max_subscribers:
        raise HTTPException(429, "Session subscriber limit reached", headers={"Retry-After": "5"})
    session.subscribers += 1
    released = False

    def release():
        nonlocal released
        if not released:
            session.subscribers -= 1
            released = True

    async def release_after_response():
        # Also covers a disconnect before the generator begins iteration.
        release()

    return EventSourceResponse(
        session.feed(revision, cursor, release=release),
        ping=15,
        send_timeout=10,
        background=BackgroundTask(release_after_response),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
