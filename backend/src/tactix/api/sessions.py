"""Bounded in-process sessions and independent resumable SSE cursors."""

import asyncio
import time
from bisect import bisect_left, bisect_right
from collections.abc import AsyncIterator, Callable
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tactix.demo.scenario import DemoBundle, build_demo
from tactix.domain.universe import Club, League
from tactix.metrics.advanced import AdvancedMetrics
from tactix.simulation.engine import MatchConfig, MatchResult, simulate_match
from tactix.simulation.replay import MatchReplay, ReplayEvent, ReplayUpdate


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    home: str = Field(default="Ashford", min_length=1, max_length=100)
    away: str = Field(default="Northbridge", min_length=1, max_length=100)
    match: MatchConfig = Field(default_factory=MatchConfig)
    speed: float = Field(default=60, gt=0, le=10000, allow_inf_nan=False)
    scenario: Literal["procedural", "ashford-demo-v1"] = "procedural"

    @model_validator(mode="after")
    def demo_configuration(self):
        if self.scenario == "ashford-demo-v1" and self.match != MatchConfig():
            raise ValueError("ashford-demo-v1 requires match-v1 seed 42 and duration 90")
        return self


class SessionInfo(BaseModel):
    session_id: str
    scenario: Literal["procedural", "ashford-demo-v1"]
    home_club_id: str
    away_club_id: str
    state: ReplayUpdate


class Session:
    def __init__(
        self,
        result: MatchResult,
        speed: float,
        now: Callable[[], float],
        demo: DemoBundle | None = None,
    ):
        self.id = str(uuid4())
        self.result = result
        self.demo = demo
        self.player = MatchReplay(result, speed=speed, now=now)
        self.metrics = AdvancedMetrics(
            result.match_id,
            result.home_club_id,
            result.away_club_id,
            result.config.duration_minutes * 60,
        )
        self.metrics.extend(result.frames)
        self.events = result.events
        self.times = [e.minute * 60 + e.second for e in self.events]
        self.start = 0
        self.closed = False
        self.subscribers = 0
        self.changed = asyncio.Event()

    def notify(self) -> None:
        self.changed.set()
        self.changed = asyncio.Event()

    def info(self) -> SessionInfo:
        return SessionInfo(
            session_id=self.id,
            scenario="ashford-demo-v1" if self.demo else "procedural",
            home_club_id=self.result.home_club_id,
            away_club_id=self.result.away_club_id,
            state=self.player.snapshot(),
        )

    def seek(self, second: float) -> None:
        self.player.seek(second)
        self.start = bisect_left(self.times, second)
        self.notify()

    def close(self) -> None:
        self.closed = True
        self.player.pause()
        self.notify()

    def resume_cursor(self, token: str | None) -> tuple[int, int]:
        state = self.player.snapshot()
        if token is None:
            return state.revision, self.start
        try:
            owner, revision_text, sequence_text = token.split(":")
            revision, sequence = int(revision_text), int(sequence_text)
            if owner != self.id or revision < 0 or sequence < 0:
                raise ValueError
        except (ValueError, TypeError):
            raise HTTPException(400, "Invalid Last-Event-ID") from None
        visible = bisect_right(self.times, state.position_seconds)
        if revision != state.revision or not self.start <= sequence <= visible:
            raise HTTPException(
                409,
                "Cursor no longer belongs to the current timeline; "
                "fetch state and reconnect without Last-Event-ID",
            )
        return revision, sequence

    async def feed(
        self, revision: int, cursor: int, *, release: Callable[[], None], tick: float = 0.1
    ) -> AsyncIterator[dict]:
        """Each reader owns its cursor; no queues, producer tasks or cursor stealing."""
        try:
            while True:
                changed = self.changed
                if self.closed:
                    yield {"event": "closed", "data": '{"session_id":"' + self.id + '"}'}
                    return
                state = self.player.snapshot()
                reset = state.revision != revision
                if reset:
                    revision, cursor = state.revision, self.start
                end = bisect_right(self.times, state.position_seconds)
                state.events = [
                    ReplayEvent(sequence=i + 1, event=self.events[i].model_copy(deep=True))
                    for i in range(cursor, end)
                ]
                cursor = end
                state.next_sequence = cursor + 1
                yield {
                    "event": "reset" if reset else "replay",
                    "id": f"{self.id}:{revision}:{cursor}",
                    "data": state.model_dump_json(),
                }
                if changed.is_set():
                    continue
                if state.status == "finished":
                    return
                if state.status == "paused":
                    await changed.wait()
                else:
                    try:
                        await asyncio.wait_for(changed.wait(), timeout=tick)
                    except TimeoutError:
                        pass
        finally:
            release()


class SessionStore:
    """Reservations bound concurrent simulation work as well as retained sessions."""

    def __init__(
        self,
        league: League,
        *,
        capacity: int = 16,
        subscribers: int = 8,
        now: Callable[[], float] = time.monotonic,
    ):
        self.league = league
        self.capacity = capacity
        self.max_subscribers = subscribers
        self.now = now
        self.sessions: dict[str, Session] = {}
        self.pending = 0

    def reserve(self) -> None:
        if len(self.sessions) + self.pending >= self.capacity:
            raise HTTPException(
                503,
                "Session capacity reached; delete an unused session",
                headers={"Retry-After": "30"},
            )
        self.pending += 1

    def club(self, selection: str) -> Club:
        for club in self.league.clubs:
            if selection in (club.id, club.name):
                return club
        raise HTTPException(404, "Unknown fictional club")

    def build(self, home: Club, away: Club, config: CreateSession) -> Session:
        if config.scenario == "ashford-demo-v1":
            if (home.name, away.name) != ("Ashford", "Northbridge"):
                raise HTTPException(
                    422, "ashford-demo-v1 requires Ashford home and Northbridge away"
                )
            demo = build_demo()
            return Session(demo.live, config.speed, self.now, demo=demo)
        result = simulate_match(home, away, config.match)
        return Session(result, config.speed, self.now)

    def get(self, session_id: str) -> Session:
        try:
            return self.sessions[session_id]
        except KeyError:
            raise HTTPException(404, "Unknown or expired session") from None

    def close(self) -> None:
        for session in self.sessions.values():
            session.close()
        self.sessions.clear()
