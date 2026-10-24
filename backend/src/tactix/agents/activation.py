"""Deterministic activation policy for model-backed match analysis.

Metrics can be refreshed on every event, while the expensive specialist fan-out only
needs to run when the match reaches a meaningful point.  This module keeps that
decision pure so a replay worker, API endpoint, or live scheduler can share it.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from tactix.domain.enums import EventType
from tactix.domain.events import Event
from tactix.domain.metrics import MetricsSnapshot

WINDOW_SECONDS = 5 * 60
DEFAULT_MOMENTUM_DELTA = 0.35


class ActivationReason(StrEnum):
    INITIAL = "initial"
    GOAL = "goal"
    MOMENTUM_SHIFT = "momentum_shift"
    WINDOW = "window"


def _event_second(event: Event) -> int:
    return event.minute * 60 + event.second


def _last_momentum(snapshot: MetricsSnapshot | None) -> float | None:
    if snapshot is None or not snapshot.momentum:
        return None
    return snapshot.momentum[-1].value


def activation_reasons(
    *,
    at_second: int,
    previous_second: int | None,
    events: Iterable[Event],
    current_metrics: MetricsSnapshot | None = None,
    previous_metrics: MetricsSnapshot | None = None,
    momentum_delta: float = DEFAULT_MOMENTUM_DELTA,
) -> tuple[ActivationReason, ...]:
    """Return why agents should run at ``at_second``.

    ``events`` should contain the events visible at the current cut.  When a previous
    cut is available, only events after it can trigger a new activation.  A revision
    reset should pass ``previous_second=None`` so the current cut is treated as an
    initial analysis rather than accidentally suppressed by an older timeline.
    """
    if type(at_second) is not int or at_second < 0:
        raise ValueError("at_second must be a nonnegative integer")
    if previous_second is not None and (
        type(previous_second) is not int or previous_second < 0
    ):
        raise ValueError("previous_second must be a nonnegative integer or None")
    if momentum_delta <= 0:
        raise ValueError("momentum_delta must be positive")

    reasons: list[ActivationReason] = []
    if previous_second is None:
        reasons.append(ActivationReason.INITIAL)
    else:
        if at_second < previous_second:
            raise ValueError("at_second cannot precede previous_second")
        if at_second // WINDOW_SECONDS > previous_second // WINDOW_SECONDS:
            reasons.append(ActivationReason.WINDOW)

    goal_after = False
    for event in events:
        second = _event_second(event)
        if second > at_second or (previous_second is not None and second <= previous_second):
            continue
        if event.type == EventType.GOAL:
            goal_after = True
            break
    if goal_after:
        reasons.append(ActivationReason.GOAL)

    before, after = _last_momentum(previous_metrics), _last_momentum(current_metrics)
    if before is not None and after is not None and abs(after - before) >= momentum_delta:
        reasons.append(ActivationReason.MOMENTUM_SHIFT)
    return tuple(dict.fromkeys(reasons))


def should_activate(**kwargs) -> bool:
    """Return whether at least one meaningful activation trigger is present."""
    return bool(activation_reasons(**kwargs))
