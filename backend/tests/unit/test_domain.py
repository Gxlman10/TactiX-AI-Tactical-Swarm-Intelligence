"""Smoke tests for the frozen domain contracts: they import, validate and reject bad input."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tactix.domain import (
    Event,
    EventType,
    MatchContext,
    Outcome,
    Player,
    Point,
    Position,
)


def test_event_builds_with_defaults() -> None:
    event = Event(
        id="e1",
        match_id="m1",
        minute=62,
        team_id="ashford",
        player_id="hartley",
        type=EventType.SHOT,
        start=Point(x=82, y=55),
    )
    assert event.outcome is Outcome.SUCCESS
    assert event.start.x == 82
    assert event.under_pressure is False


def test_player_rejects_out_of_range_attribute() -> None:
    with pytest.raises(ValidationError):
        Player(
            id="p1",
            name="Test Player",
            number=9,
            positions=[Position.ST],
            physical={"pace": 150},  # above the 0-100 scale
        )


def test_match_context_starts_empty() -> None:
    ctx = MatchContext(match_id="m1")
    assert ctx.analyst_findings == []
    assert ctx.historian_findings == []
    assert ctx.conflicts == []
    assert ctx.degraded == []
