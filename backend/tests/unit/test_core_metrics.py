"""Known scoreboards, denominator evidence and incremental snapshot semantics."""

import json
import subprocess
import sys

import pytest

from tactix.domain.common import Point
from tactix.domain.enums import EventType, Outcome, PossessionPhase, ShotOutcome
from tactix.domain.events import Event, Possession
from tactix.domain.metrics import MetricsSnapshot
from tactix.metrics.core import CoreMetrics, metrics_for_match
from tactix.simulation.engine import MatchConfig, PossessionFrame, simulate_match
from tactix.universe.generator import generate_league


def event(key, at, team, player, kind, **kwargs):
    return Event(
        id=key,
        match_id="known",
        minute=at // 60,
        second=at % 60,
        team_id=team,
        player_id=player,
        type=kind,
        start=Point(x=50, y=50),
        **kwargs,
    )


def frame(key, team, start, end, events, outcome="shot"):
    for item in events:
        item.possession_id = key
    return PossessionFrame(
        possession=Possession(
            id=key,
            match_id="known",
            team_id=team,
            start_minute=start // 60,
            start_second=start % 60,
            end_minute=end // 60,
            end_second=end % 60,
            phase=PossessionPhase.OUTCOME,
            outcome=outcome,
            event_ids=[e.id for e in events],
        ),
        phases=[PossessionPhase.BUILD_UP, PossessionPhase.OUTCOME],
        events=events,
    )


def known_frames():
    first = frame(
        "p1",
        "a",
        0,
        30,
        [
            event("kick1", 0, "a", "a1", EventType.KICKOFF),
            event(
                "a-pass1", 5, "a", "a1", EventType.PASS, related_player_id="a2", progressive=True
            ),
            event(
                "a-shot1",
                30,
                "a",
                "a2",
                EventType.SHOT,
                shot_outcome=ShotOutcome.SAVED,
                outcome=Outcome.FAIL,
            ),
            event("b-save", 30, "b", "bk", EventType.SAVE, related_player_id="a2"),
        ],
        "saved",
    )
    second = frame(
        "p2",
        "b",
        30,
        50,
        [
            event("kick2", 30, "b", "bk", EventType.GOAL_KICK),
            event("a-press", 50, "a", "a1", EventType.PRESS, related_player_id="bk"),
            event(
                "b-pass1",
                50,
                "b",
                "bk",
                EventType.PASS,
                related_player_id="b1",
                outcome=Outcome.FAIL,
                under_pressure=True,
                pressured_by="a1",
            ),
        ],
        "turnover",
    )
    recovery = event("a-recovery", 50, "a", "a1", EventType.RECOVERY)
    recovery.start = Point(x=78, y=50)
    third = frame(
        "p3",
        "a",
        50,
        80,
        [
            recovery,
            event("a-pass2", 55, "a", "a1", EventType.PASS, related_player_id="a3"),
            event(
                "a-shot2",
                80,
                "a",
                "a3",
                EventType.SHOT,
                shot_outcome=ShotOutcome.OFF_TARGET,
                outcome=Outcome.FAIL,
            ),
        ],
        "off_target",
    )
    fourth = frame(
        "p4",
        "b",
        80,
        100,
        [
            event("kick3", 80, "b", "bk", EventType.GOAL_KICK),
            event("b-pass2", 85, "b", "bk", EventType.PASS, related_player_id="b2"),
            event("b-shot", 100, "b", "b2", EventType.SHOT, shot_outcome=ShotOutcome.GOAL),
            event("b-goal", 100, "b", "b2", EventType.GOAL, subtype="from_shot:b-shot"),
        ],
        "goal",
    )
    fifth = frame(
        "p5",
        "a",
        100,
        120,
        [
            event("kick4", 100, "a", "a1", EventType.KICKOFF),
            event(
                "a-pass3",
                120,
                "a",
                "a1",
                EventType.PASS,
                related_player_id="a2",
                outcome=Outcome.FAIL,
            ),
        ],
        "turnover",
    )
    return [first, second, third, fourth, fifth]


def values(snapshot, team):
    return {m.key: m for t in snapshot.teams if t.team_id == team for m in t.values}


def build_known():
    engine = CoreMetrics("known", "a", "b", 120)
    engine.extend(known_frames())
    return engine


def test_known_counts_and_time_percentages():
    snapshot = build_known().snapshot()
    a, b = values(snapshot, "a"), values(snapshot, "b")
    expected_a = {
        "possession_seconds": 80,
        "possessions": 3,
        "passes_attempted": 3,
        "passes_completed": 2,
        "progressive_passes": 1,
        "shots": 2,
        "shots_on_target": 1,
        "shots_off_target": 1,
        "shots_blocked": 0,
        "goals": 0,
        "saves": 0,
        "pressures": 1,
        "pressure_successes": 1,
        "recoveries": 1,
        "high_recoveries": 1,
        "turnovers": 1,
    }
    expected_b = {
        "possession_seconds": 40,
        "possessions": 2,
        "passes_attempted": 2,
        "passes_completed": 1,
        "shots": 1,
        "shots_on_target": 1,
        "goals": 1,
        "saves": 1,
        "pressures": 0,
        "pressure_successes": 0,
        "turnovers": 1,
    }
    assert all(a[key].value == number for key, number in expected_a.items())
    assert all(b[key].value == number for key, number in expected_b.items())
    assert a["possession_pct"].value == pytest.approx(66.6667)
    assert b["possession_pct"].value == pytest.approx(33.3333)
    assert a["possession_pct"].value + b["possession_pct"].value == 100
    assert a["pass_accuracy_pct"].value == pytest.approx(66.6667)
    assert a["pass_share_pct"].value == 60 and b["pass_share_pct"].value == 40
    assert a["shot_accuracy_pct"].value == 50 and b["shot_accuracy_pct"].value == 100
    assert a["pressure_success_pct"].value == 100
    assert "pressure_success_pct" not in b


def test_evidence_contains_denominators_and_pressure_causes():
    snapshot = build_known().snapshot()
    a, b = values(snapshot, "a"), values(snapshot, "b")
    assert a["pass_accuracy_pct"].evidence.event_ids == ["a-pass1", "a-pass2", "a-pass3"]
    assert a["pass_share_pct"].evidence.event_ids == [
        "a-pass1",
        "b-pass1",
        "a-pass2",
        "b-pass2",
        "a-pass3",
    ]
    assert a["pressure_successes"].evidence.event_ids == ["a-press", "b-pass1"]
    assert b["goals"].evidence.event_ids == ["b-goal"]
    assert b["shots"].evidence.event_ids == ["b-shot"]
    assert all(metric.evidence.description for team in snapshot.teams for metric in team.values)


@pytest.mark.parametrize("cutoff", [0, 5, 30, 50, 60, 80, 99, 100, 120])
def test_snapshots_never_leak_future_evidence(cutoff):
    engine = build_known()
    snapshot = engine.snapshot(cutoff)
    source = {e.id: e for f in known_frames() for e in f.events}
    for team in snapshot.teams:
        for metric in team.values:
            assert all(
                source[key].minute * 60 + source[key].second <= cutoff
                for key in metric.evidence.event_ids
            )
    if cutoff < 100:
        assert values(snapshot, "b")["goals"].value == 0
    assert snapshot.minute == cutoff // 60


def test_cutoff_truncates_an_active_possession_and_excludes_future_outcomes():
    snapshot = build_known().snapshot(60)
    a, b = values(snapshot, "a"), values(snapshot, "b")
    assert a["possession_seconds"].value == 40 and b["possession_seconds"].value == 20
    assert a["shots"].value == 1 and a["shots_off_target"].value == 0
    assert a["passes_attempted"].value == 2 and a["pass_accuracy_pct"].value == 100
    assert a["turnovers"].value == 0


def test_empty_data_and_zero_denominators_are_not_invented_rates():
    engine = CoreMetrics("known", "a", "b", 120)
    empty = engine.snapshot()
    for team in empty.teams:
        assert all(m.value == 0 for m in team.values)
        assert all(not m.key.endswith("_pct") for m in team.values)
    engine.push(known_frames()[0])
    at_start = values(engine.snapshot(0), "a")
    assert at_start["possessions"].value == 1
    assert "possession_pct" not in at_start


def test_dead_time_is_excluded_and_incremental_equals_complete():
    frames = known_frames()
    # Leave 20 seconds with no possession between frames, preserving event-local times.
    frames[0].possession.end_second = 10
    frames[0].events = frames[0].events[:2]
    frames[0].possession.event_ids = [e.id for e in frames[0].events]
    engine = CoreMetrics("known", "a", "b", 120)
    engine.extend(frames)
    snapshot = engine.snapshot()
    assert sum(values(snapshot, team)["possession_seconds"].value for team in ("a", "b")) == 100
    incremental = CoreMetrics("known", "a", "b", 120)
    for item in frames:
        incremental.push(item)
        incremental.snapshot()
    assert incremental.snapshot() == snapshot


def test_inputs_and_returned_snapshots_are_independent():
    frames = known_frames()
    engine = CoreMetrics("known", "a", "b", 120)
    engine.extend(frames[:4])
    before = engine.snapshot()
    saved = before.model_dump_json()
    frames[0].events.clear()
    assert engine.snapshot() == before
    engine.push(frames[4])
    assert before.model_dump_json() == saved
    before.teams[0].values.clear()
    assert engine.snapshot().teams[0].values


@pytest.mark.parametrize("change", ["ids", "time", "team", "links", "goal", "pressure", "receiver"])
def test_invalid_frames_are_rejected_atomically(change):
    engine = CoreMetrics("known", "a", "b", 120)
    frames = known_frames()
    if change == "ids":
        bad = frames[0]
        bad.events[1].id = bad.events[0].id
    elif change == "time":
        bad = frames[0]
        bad.events[0].minute = 2
    elif change == "team":
        bad = frames[0]
        bad.events[0].team_id = "unknown"
    elif change == "links":
        bad = frames[0]
        bad.possession.event_ids.clear()
    elif change == "goal":
        bad = frames[3]
        bad.events[-1].subtype = "from_shot:missing"
    elif change == "pressure":
        bad = frames[1]
        bad.events[-1].pressured_by = "other-presser"
    else:
        bad = frames[0]
        bad.events[1].related_player_id = "a1"
    before = engine.snapshot().model_dump_json()
    with pytest.raises(ValueError):
        engine.push(bad)
    assert engine.snapshot().model_dump_json() == before


def test_duplicate_delivery_is_rejected_and_not_recounted():
    engine = build_known()
    before = engine.snapshot()
    with pytest.raises(ValueError, match="Duplicate"):
        engine.push(known_frames()[0])
    assert engine.snapshot() == before


def test_block_markers_and_goalposts_do_not_inflate_shot_counts():
    engine = CoreMetrics("known", "a", "b", 60)
    engine.extend(
        [
            frame(
                "one",
                "a",
                0,
                10,
                [
                    event("k", 0, "a", "a1", EventType.KICKOFF),
                    event(
                        "s1",
                        10,
                        "a",
                        "a1",
                        EventType.SHOT,
                        shot_outcome=ShotOutcome.BLOCKED,
                        outcome=Outcome.FAIL,
                    ),
                    event("block", 10, "b", "b1", EventType.BLOCK, related_player_id="a1"),
                ],
                "corner",
            ),
            frame(
                "two",
                "a",
                10,
                20,
                [
                    event("corner", 10, "a", "a1", EventType.CORNER),
                    event(
                        "s2",
                        20,
                        "a",
                        "a1",
                        EventType.SHOT,
                        shot_outcome=ShotOutcome.POST,
                        outcome=Outcome.FAIL,
                    ),
                ],
            ),
        ]
    )
    a = values(engine.snapshot(), "a")
    assert a["shots"].value == 2 and a["shots_blocked"].value == 1
    assert a["shots_off_target"].value == 1 and a["shots_on_target"].value == 0
    assert a["shot_accuracy_pct"].value == 0


def test_false_turnover_and_open_possession_are_rejected():
    bad = known_frames()[0]
    bad.possession.outcome = "turnover"
    engine = CoreMetrics("known", "a", "b", 120)
    with pytest.raises(ValueError, match="terminal failed"):
        engine.push(bad)
    bad = known_frames()[0]
    bad.possession.phase = PossessionPhase.BUILD_UP
    with pytest.raises(ValueError, match="complete"):
        engine.push(bad)


@pytest.mark.parametrize("cutoff", [-1, 121, True, 1.5])
def test_invalid_snapshot_cuts(cutoff):
    with pytest.raises(ValueError):
        build_known().snapshot(cutoff)


def test_simulation_integration_score_and_live_equivalence(tmp_path):
    clubs = generate_league().clubs[:2]
    match = simulate_match(*clubs, MatchConfig(duration_minutes=10))
    source_json = match.model_dump_json()
    snapshot = metrics_for_match(match)
    assert (
        tuple(
            values(snapshot, team)["goals"].value
            for team in (match.home_club_id, match.away_club_id)
        )
        == match.score
    )
    assert sum(
        values(snapshot, team)["shots"].value for team in (match.home_club_id, match.away_club_id)
    ) == sum(e.type == EventType.SHOT for e in match.events)
    incremental = CoreMetrics(match.match_id, match.home_club_id, match.away_club_id, 600)
    incremental.extend(match.frames)
    assert incremental.snapshot(600) == snapshot
    assert match.model_dump_json() == source_json
    input_path, output = tmp_path / "match.json", tmp_path / "metrics.json"
    input_path.write_text(source_json, encoding="utf-8")
    args = [
        sys.executable,
        "-m",
        "tactix.metrics",
        "--input",
        str(input_path),
        "--output",
        str(output),
    ]
    subprocess.run(args, check=True, capture_output=True, text=True)
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["metrics_version"] == "core-v1" and artifact["at_second"] == 600
    assert MetricsSnapshot.model_validate(artifact["snapshot"]) == snapshot
    failed = subprocess.run(args, capture_output=True, text=True)
    assert failed.returncode == 2
