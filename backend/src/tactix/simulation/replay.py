"""Monotonic match playback with stable cursors and explicit timeline revisions."""

import argparse
import asyncio
import math
import time
from bisect import bisect_left, bisect_right
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from tactix.domain.enums import EventType
from tactix.domain.events import Event
from tactix.metrics.core import CoreMetrics
from tactix.simulation.engine import MatchResult

REPLAY_VERSION = "replay-v1"


class ReplayEvent(BaseModel):
    sequence: int  # Stable one-based index in the original match event list.
    event: Event


class ReplayUpdate(BaseModel):
    replay_version: str = REPLAY_VERSION
    match_id: str
    revision: int
    position_seconds: float
    duration_seconds: int
    speed: float
    status: Literal["paused", "playing", "finished"]
    next_sequence: int
    score: tuple[int, int]
    events: list[ReplayEvent]


def _number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


class MatchReplay:
    """One timeline and one delivery cursor, owned by a single event loop.

    poll() supports synchronous adapters and fake clocks. stream() adds interruptible
    asynchronous scheduling; simultaneous consumers are rejected rather than racing.
    """

    def __init__(
        self, result: MatchResult, *, speed: float = 1, now: Callable[[], float] = time.monotonic
    ):
        speed = self._speed_value(speed)
        duration = result.config.duration_minutes * 60
        validator = CoreMetrics(result.match_id, result.home_club_id, result.away_club_id, duration)
        validator.extend(result.frames)
        if not result.frames:
            raise ValueError("Replay requires a nonempty match")
        self.match_id = result.match_id
        self.duration = duration
        self._teams = (result.home_club_id, result.away_club_id)
        self._events = [event.model_copy(deep=True) for event in result.events]
        self._times = [e.minute * 60 + e.second for e in self._events]
        self._goal_times = [
            [
                self._times[i]
                for i, e in enumerate(self._events)
                if e.type == EventType.GOAL and e.team_id == team
            ]
            for team in self._teams
        ]
        self._now = now
        self._speed = speed
        self._position = 0.0
        self._anchor = now()
        self._status = "paused"
        self._cursor = 0
        self._revision = 0
        self._wake = asyncio.Event()
        self._streaming = False

    @staticmethod
    def _speed_value(value: float) -> float:
        value = _number(value, "speed")
        if value <= 0:
            raise ValueError("speed must be positive")
        return value

    def _sync(self) -> None:
        current = self._now()
        if self._status == "playing":
            self._position = min(
                self.duration, self._position + (current - self._anchor) * self._speed
            )
            if self._position >= self.duration:
                self._status = "finished"
        self._anchor = current

    def play(self) -> None:
        self._sync()
        if self._status != "finished":
            self._status = "playing"
        self._wake.set()

    def pause(self) -> None:
        self._sync()
        if self._status != "finished":
            self._status = "paused"
        self._wake.set()

    def set_speed(self, speed: float) -> None:
        speed = self._speed_value(speed)
        self._sync()
        self._speed = speed
        self._wake.set()

    def seek(self, second: float) -> None:
        second = _number(second, "seek second")
        if not 0 <= second <= self.duration:
            raise ValueError("seek second must be inside the match")
        self._position = second
        self._anchor = self._now()
        self._cursor = bisect_left(self._times, second)
        self._revision += 1
        self._status = "finished" if second == self.duration else "paused"
        self._wake.set()

    def _update(self, deliver: bool) -> ReplayUpdate:
        self._sync()
        end = bisect_right(self._times, self._position)
        events = (
            [
                ReplayEvent(sequence=i + 1, event=self._events[i].model_copy(deep=True))
                for i in range(self._cursor, end)
            ]
            if deliver
            else []
        )
        if deliver:
            self._cursor = end
        return ReplayUpdate(
            match_id=self.match_id,
            revision=self._revision,
            position_seconds=self._position,
            duration_seconds=self.duration,
            speed=self._speed,
            status=self._status,
            next_sequence=self._cursor + 1,
            score=tuple(bisect_right(times, self._position) for times in self._goal_times),
            events=events,
        )

    def snapshot(self) -> ReplayUpdate:
        """Observe clock and scoreboard without consuming pending events."""
        return self._update(False)

    def poll(self) -> ReplayUpdate:
        """Deliver every due event exactly once since the last poll or seek."""
        if self._streaming:
            raise RuntimeError("The active stream owns event delivery")
        return self._update(True)

    async def stream(self, *, tick_seconds: float = 0.1) -> AsyncIterator[ReplayUpdate]:
        """Yield clock ticks and due batches; closing/cancellation pauses playback.

        Start explicitly with play(). Paused streams wait for a control instead of
        producing repeated idle ticks. No background producer or unbounded queue.
        """
        tick_seconds = _number(tick_seconds, "tick_seconds")
        if not 0.001 <= tick_seconds <= 60:
            raise ValueError("tick_seconds must be between 0.001 and 60")
        if self._streaming:
            raise RuntimeError("Only one replay stream may consume events")
        self._streaming = True
        try:
            while True:
                self._wake.clear()
                update = self._update(True)
                yield update
                if self._revision != update.revision or self._wake.is_set():
                    continue
                if update.status == "finished":
                    return
                if update.status == "paused":
                    await self._wake.wait()
                    continue
                target = (
                    self._times[self._cursor] if self._cursor < len(self._times) else self.duration
                )
                # Consumer processing time counts towards playback, not an extra delay.
                self._sync()
                delay = min(tick_seconds, max(0, (target - self._position) / self._speed))
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=delay)
                except TimeoutError:
                    pass
        finally:
            self.pause()
            self._streaming = False


async def _print_stream(player: MatchReplay, tick: float) -> None:
    player.play()
    async for update in player.stream(tick_seconds=tick):
        print(update.model_dump_json(), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Full MatchResult JSON")
    parser.add_argument("--speed", type=float, default=1)
    parser.add_argument("--start-second", type=float, default=0)
    parser.add_argument("--tick-seconds", type=float, default=0.1)
    args = parser.parse_args()
    try:
        result = MatchResult.model_validate_json(args.input.read_text(encoding="utf-8"))
        player = MatchReplay(result, speed=args.speed)
        if args.start_second:
            player.seek(args.start_second)
        asyncio.run(_print_stream(player, args.tick_seconds))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
