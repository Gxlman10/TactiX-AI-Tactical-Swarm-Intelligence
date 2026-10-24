from tactix.agents.activation import ActivationReason, activation_reasons, should_activate
from tactix.domain.enums import EventType
from tactix.domain.metrics import MetricsSnapshot, MomentumPoint


def event(event_type: EventType, minute: int, second: int = 0):
    from tactix.domain.common import Point
    from tactix.domain.events import Event

    return Event(
        id=f"{event_type}-{minute}-{second}",
        match_id="match",
        minute=minute,
        second=second,
        team_id="home",
        player_id="player",
        type=event_type,
        start=Point(x=50, y=50),
    )


def metrics(value: float) -> MetricsSnapshot:
    return MetricsSnapshot(
        match_id="match", minute=30, momentum=[MomentumPoint(minute=30, value=value)]
    )


def test_initial_cut_activates_once_even_without_a_goal():
    reasons = activation_reasons(
        at_second=0, previous_second=None, events=[], current_metrics=metrics(0)
    )

    assert reasons == (ActivationReason.INITIAL,)
    assert should_activate(at_second=0, previous_second=None, events=[])


def test_goal_activates_but_ordinary_events_do_not():
    assert activation_reasons(
        at_second=3720,
        previous_second=3600,
        events=[event(EventType.PASS, 61, 59)],
    ) == ()
    assert activation_reasons(
        at_second=3720,
        previous_second=3600,
        events=[event(EventType.GOAL, 62)],
    ) == (ActivationReason.GOAL,)


def test_crossing_five_minute_window_activates():
    assert activation_reasons(
        at_second=600, previous_second=299, events=[]
    ) == (ActivationReason.WINDOW,)


def test_momentum_shift_activates_when_threshold_is_reached():
    assert activation_reasons(
        at_second=1795,
        previous_second=1790,
        events=[],
        previous_metrics=metrics(-0.2),
        current_metrics=metrics(0.15),
    ) == (ActivationReason.MOMENTUM_SHIFT,)


def test_old_goal_does_not_retrigger_the_same_revision():
    assert activation_reasons(
        at_second=3720,
        previous_second=3600,
        events=[event(EventType.GOAL, 40)],
    ) == ()
