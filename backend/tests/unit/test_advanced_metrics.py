"""Known directed graphs, spatial boundaries and auditable match-time cuts."""

import json
import subprocess
import sys

import pytest

from tactix.domain.common import Point
from tactix.domain.enums import EventType, Outcome, PossessionPhase, ShotOutcome
from tactix.domain.events import Event, Possession
from tactix.metrics.advanced import AdvancedMetrics, _betweenness, advanced_metrics_for_match
from tactix.metrics.core import metrics_for_match
from tactix.simulation.engine import MatchConfig, PossessionFrame, simulate_match
from tactix.universe.generator import generate_league


def event(key, at, team="a", player="a1", kind=EventType.PASS, x=70, **kwargs):
    if kind == EventType.PASS:
        kwargs.setdefault("related_player_id", "a2" if team == "a" else "b2")
        kwargs.setdefault("end", Point(x=80, y=30))
    return Event(
        id=key,
        match_id="m",
        minute=at // 60,
        second=at % 60,
        team_id=team,
        player_id=player,
        type=kind,
        start=Point(x=x, y=50),
        **kwargs,
    )


def frame(key, owner, events):
    for e in events:
        e.possession_id = key
    first, last = events[0], events[-1]
    return PossessionFrame(
        possession=Possession(
            id=key,
            match_id="m",
            team_id=owner,
            start_minute=first.minute,
            start_second=first.second,
            end_minute=last.minute,
            end_second=last.second,
            phase=PossessionPhase.OUTCOME,
            event_ids=[e.id for e in events],
        ),
        events=events,
        phases=[PossessionPhase.OUTCOME],
    )


def values(snapshot, index=0):
    return {v.key: v for v in snapshot.teams[index].values}


def engine(*frames):
    accumulator = AdvancedMetrics("m", "a", "b")
    accumulator.extend(frames)
    return accumulator


def test_known_network_chain_weights_locations_and_evidence():
    source = frame(
        "p",
        "a",
        [
            event("ab1", 0),
            event("ab2", 1),
            event("bc", 2, player="a2", related_player_id="a3", x=80),
            event("failed", 3, player="a3", related_player_id="a4", outcome=Outcome.FAIL),
        ],
    )
    snapshot = engine(source).snapshot()
    network = snapshot.teams[0].pass_network
    assert [(e.from_player_id, e.to_player_id, e.passes) for e in network.edges] == [
        ("a1", "a2", 2),
        ("a2", "a3", 1),
    ]
    nodes = {n.player_id: n for n in network.nodes}
    assert set(nodes) == {"a1", "a2", "a3"}
    assert nodes["a2"].degree_centrality == 0.5
    assert nodes["a2"].betweenness_centrality == 0.5
    assert nodes["a2"].touches == 3
    assert nodes["a2"].avg_location == Point(x=80, y=36.6667)
    assert values(snapshot)["pass_network_passes"].evidence.event_ids == ["ab1", "ab2", "bc"]


def test_diamond_equal_shortest_paths_and_disconnected_nodes():
    result = _betweenness({"a": {"b", "c"}, "b": {"d"}, "c": {"d"}, "d": set(), "isolated": set()})
    assert result == {"a": 0, "b": 0.0417, "c": 0.0417, "d": 0, "isolated": 0}


def test_reciprocal_graph_and_two_node_normalization():
    snapshot = engine(
        frame("p", "a", [event("ab", 0), event("ba", 1, player="a2", related_player_id="a1")])
    ).snapshot()
    assert all(
        n.degree_centrality == 1 and n.betweenness_centrality == 0
        for n in snapshot.teams[0].pass_network.nodes
    )


def test_field_tilt_uses_both_teams_completed_pass_starts_in_own_coordinates():
    first = frame(
        "p1",
        "a",
        [
            event("a1", 0, x=200 / 3),
            event("a2", 1, x=80),
            event("below", 2, x=66),
            event("failed", 3, outcome=Outcome.FAIL),
        ],
    )
    second = frame("p2", "b", [event("b1", 4, "b", "b1", x=90)])
    snapshot = engine(first, second).snapshot()
    assert values(snapshot)["field_tilt"].value == 66.6667
    assert values(snapshot, 1)["field_tilt"].value == 33.3333
    assert values(snapshot)["field_tilt"].evidence.event_ids == ["a1", "a2", "b1"]


def test_ppda_boundaries_opposing_coordinates_and_action_classification():
    source = frame(
        "p",
        "b",
        [
            event("pass-in", 0, "b", "b1", x=60),
            event("pass-out", 1, "b", "b1", x=60.001),
            event("failed-in", 2, "b", "b1", x=10, outcome=Outcome.FAIL),
            event("tackle", 3, kind=EventType.TACKLE, x=40),
            event("interception", 4, kind=EventType.INTERCEPTION, x=70),
            event("foul", 5, kind=EventType.FOUL, x=40, outcome=Outcome.FAIL),
            event("duel", 6, kind=EventType.DUEL, x=50),
            event("low", 7, kind=EventType.TACKLE, x=39.999),
            event("miss", 8, kind=EventType.TACKLE, x=60, outcome=Outcome.FAIL),
            event("press", 9, kind=EventType.PRESS, x=60, outcome=Outcome.FAIL),
        ],
    )
    result = values(engine(source).snapshot())
    assert result["ppda"].value == 0.5
    assert result["ppda_opponent_passes"].value == 2
    assert result["ppda_defensive_actions"].value == 4
    assert result["ppda"].evidence.event_ids == [
        "pass-in",
        "failed-in",
        "tackle",
        "interception",
        "foul",
        "duel",
    ]


def test_zero_denominators_omitted_and_real_zero_is_present():
    empty = engine().snapshot()
    assert "ppda" not in values(empty) and "field_tilt" not in values(empty)
    assert values(empty)["xg_like"].value == 0
    assert empty.teams[0].pass_network.nodes == []
    snapshot = engine(frame("p", "b", [event("t", 0, kind=EventType.TACKLE)])).snapshot()
    assert values(snapshot)["ppda"].value == 0


def test_shot_values_goal_deduplication_and_cutoff():
    source = frame(
        "p",
        "a",
        [
            event(
                "miss",
                0,
                kind=EventType.SHOT,
                expected_value=0.1,
                shot_outcome=ShotOutcome.OFF_TARGET,
                outcome=Outcome.FAIL,
            ),
            event(
                "scoring-shot",
                10,
                kind=EventType.SHOT,
                expected_value=0.3,
                shot_outcome=ShotOutcome.GOAL,
            ),
            event("goal", 10, kind=EventType.GOAL, subtype="from_shot:scoring-shot"),
        ],
    )
    accumulator = engine(source)
    full = accumulator.snapshot(10)
    assert values(full)["xg_like"].value == 0.4
    assert values(full)["xg_like"].evidence.event_ids == ["miss", "scoring-shot"]
    assert len(full.teams[0].shot_map) == 2
    assert full.teams[0].shot_map[1].event_id == "scoring-shot"
    assert values(accumulator.snapshot(9))["xg_like"].value == 0.1
    assert len(accumulator.snapshot(9).teams[0].shot_map) == 1


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -0.01, 1.01])
def test_invalid_xg_rejected_atomically(bad):
    accumulator = engine()
    before = accumulator.snapshot()
    source = frame(
        "p",
        "a",
        [
            event(
                "shot",
                0,
                kind=EventType.SHOT,
                expected_value=bad,
                shot_outcome=ShotOutcome.OFF_TARGET,
            )
        ],
    )
    with pytest.raises(ValueError, match="expected_value"):
        accumulator.push(source)
    assert accumulator.snapshot() == before
    source.events[0].expected_value = 0.5
    accumulator.push(source)
    assert values(accumulator.snapshot())["xg_like"].value == 0.5


def test_missing_pass_endpoint_and_wrong_defensive_owner_rejected():
    with pytest.raises(ValueError, match="endpoint"):
        engine(frame("p", "a", [event("pass", 0, end=None)]))
    with pytest.raises(ValueError, match="opposing"):
        engine(frame("p", "a", [event("t", 0, kind=EventType.TACKLE)]))


def test_sources_snapshots_are_isolated_and_future_passes_hidden():
    source = frame("p", "a", [event("ab", 0), event("bc", 10, player="a2", related_player_id="a3")])
    accumulator = engine(source)
    before = accumulator.snapshot(9)
    assert [n.player_id for n in before.teams[0].pass_network.nodes] == ["a1", "a2"]
    source.events[0].start.x = 1
    before.teams[0].pass_network.nodes.clear()
    assert len(accumulator.snapshot(9).teams[0].pass_network.nodes) == 2
    assert accumulator.snapshot(9).teams[0].pass_network.nodes[0].avg_location.x == 70


@pytest.fixture(scope="module")
def match():
    league = generate_league()
    return simulate_match(league.clubs[0], league.clubs[1], MatchConfig(duration_minutes=6))


def test_generated_match_incremental_batch_core_compatibility_and_evidence(match):
    accumulator = AdvancedMetrics(match.match_id, match.home_club_id, match.away_club_id, 360)
    for index, source in enumerate(match.frames):
        accumulator.push(source)
        at = source.possession.end_minute * 60 + source.possession.end_second
        observed = match.model_copy(update={"frames": match.frames[: index + 1]})
        assert accumulator.snapshot() == advanced_metrics_for_match(observed, at)
    full = advanced_metrics_for_match(match)
    core = metrics_for_match(match)
    visible_ids = {e.id for e in match.events}
    for rich, basic in zip(full.teams, core.teams, strict=True):
        assert rich.values[: len(basic.values)] == basic.values
        assert sum(e.passes for e in rich.pass_network.edges) == next(
            v.value for v in basic.values if v.key == "passes_completed"
        )
        assert all(set(v.evidence.event_ids) <= visible_ids for v in rich.values)
    cut = advanced_metrics_for_match(match, 100)
    allowed = {e.id for e in match.events if e.minute * 60 + e.second <= 100}
    assert all(set(v.evidence.event_ids) <= allowed for t in cut.teams for v in t.values)


def test_cli_advanced_version_and_exclusive_output(match, tmp_path):
    source, destination = tmp_path / "match.json", tmp_path / "metrics.json"
    source.write_text(match.model_dump_json(), encoding="utf-8")
    args = [
        sys.executable,
        "-m",
        "tactix.metrics",
        "--input",
        str(source),
        "--advanced",
        "--at-second",
        "100",
        "--output",
        str(destination),
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    actual = json.loads(destination.read_text(encoding="utf-8"))
    assert actual["metrics_version"] == "advanced-v1"
    assert actual["snapshot"] == advanced_metrics_for_match(match, 100).model_dump(mode="json")
    before = destination.read_bytes()
    assert subprocess.run(args, capture_output=True).returncode != 0
    assert destination.read_bytes() == before
