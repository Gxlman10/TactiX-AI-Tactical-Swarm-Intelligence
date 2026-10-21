"""State-machine behavior, references and stream/export contracts."""

import json
import math
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

import pytest
from pydantic import ValidationError

from tactix.domain.common import Point
from tactix.domain.enums import BuildUpStyle, EventType, Outcome, Position, ShotOutcome
from tactix.domain.events import Event
from tactix.domain.universe import Player
from tactix.simulation.engine import (
    MatchConfig,
    MatchResult,
    iter_events,
    iter_possessions,
    simulate_match,
)
from tactix.simulation.rules import (
    action_probability,
    direction,
    distance,
    fatigue,
    pitch_zone,
    shot_value,
)
from tactix.simulation.validation import validate_match
from tactix.universe.generator import LeagueConfig, generate_league


@pytest.fixture(scope="module")
def clubs():
    league = generate_league()
    return league.clubs[0], league.clubs[1]


@pytest.mark.parametrize("seed", [0, 1, 42, 2026, 2**63 - 1])
@pytest.mark.parametrize("duration", [2, 3, 10, 90])
def test_match_invariants_and_period_boundaries(clubs, seed, duration):
    home, away = clubs
    result = simulate_match(home, away, MatchConfig(seed=seed, duration_minutes=duration))
    validate_match(result, home, away)
    events = result.events
    assert len({e.id for e in events}) == len(events)
    times = [e.minute * 60 + e.second for e in events]
    assert times == sorted(times)
    assert min(times) == 0 and max(times) <= duration * 60
    halftime = [
        e
        for e in events
        if e.type == EventType.KICKOFF and e.minute * 60 + e.second == duration * 30
    ]
    assert len(halftime) == 1 and halftime[0].team_id == away.id
    assert result.score == (
        sum(e.type == EventType.GOAL and e.team_id == home.id for e in events),
        sum(e.type == EventType.GOAL and e.team_id == away.id for e in events),
    )
    assert sum(result.score) == sum(
        e.type == EventType.SHOT and e.shot_outcome == ShotOutcome.GOAL for e in events
    )
    assert MatchResult.model_validate_json(result.model_dump_json()) == result


def test_same_seed_streams_equal_and_lineups_are_not_mutated(clubs):
    home, away = clubs
    originals = (home.model_dump_json(), away.model_dump_json())
    global_state = random.getstate()
    config = MatchConfig(duration_minutes=10)
    result = simulate_match(home, away, config)
    assert result.model_dump_json() == simulate_match(home, away, config).model_dump_json()
    assert result.frames == list(iter_possessions(home, away, config))
    assert result.events == list(iter_events(home, away, config))
    assert global_state == random.getstate()
    assert originals == (home.model_dump_json(), away.model_dump_json())
    different = simulate_match(home, away, MatchConfig(seed=43, duration_minutes=10))
    assert result.match_id != different.match_id
    assert {e.id for e in result.events}.isdisjoint(e.id for e in different.events)


def test_iteration_snapshots_source_before_first_frame(clubs):
    home, away = (club.model_copy(deep=True) for club in clubs)
    config = MatchConfig(duration_minutes=10)
    frames = iter_possessions(home, away, config)
    expected = simulate_match(home, away, config).frames
    first = next(frames)
    home.squad[0].physical.pace = 0
    home.tactical_identity.tempo = 100
    assert [first, *frames] == expected


def test_successful_pass_receiver_becomes_next_ball_actor(clubs):
    result = simulate_match(*clubs)
    checked = 0
    for frame in result.frames:
        active = [
            e
            for e in frame.events
            if e.team_id == frame.possession.team_id
            and e.type
            in (
                EventType.PASS,
                EventType.CARRY,
                EventType.DRIBBLE,
                EventType.SHOT,
                EventType.CLEARANCE,
            )
        ]
        for previous, following in zip(active, active[1:], strict=False):
            if previous.type == EventType.PASS and previous.outcome == Outcome.SUCCESS:
                assert following.player_id == previous.related_player_id
                assert following.start == previous.end
                checked += 1
            elif previous.type in (EventType.CARRY, EventType.DRIBBLE):
                assert following.player_id == previous.player_id
    assert checked > 20


def test_outcome_coverage_and_goal_links(clubs):
    result = simulate_match(*clubs)
    kinds = Counter(e.type for e in result.events)
    assert all(
        kinds[kind]
        for kind in (
            EventType.PASS,
            EventType.CARRY,
            EventType.DRIBBLE,
            EventType.PRESS,
            EventType.RECOVERY,
            EventType.SHOT,
            EventType.GOAL,
            EventType.SAVE,
            EventType.BLOCK,
            EventType.CORNER,
            EventType.FREE_KICK,
            EventType.GOAL_KICK,
        )
    )
    by_id = {e.id: e for e in result.events}
    for event in result.events:
        if event.type == EventType.GOAL:
            shot = by_id[event.subtype.removeprefix("from_shot:")]
            assert shot.type == EventType.SHOT and shot.shot_outcome == ShotOutcome.GOAL
            assert event.expected_value is None


def test_fatigue_pressure_and_skill_have_causal_effects():
    player = Player(
        id="p",
        name="P",
        number=1,
        positions=[Position.CM],
        physical={"stamina": 90},
        technical={"passing": 90, "long_passing": 30},
    )
    fresh = action_probability(player, EventType.PASS, 10, 0, False)
    assert action_probability(player, EventType.PASS, 10, 90, False) < fresh
    assert action_probability(player, EventType.PASS, 10, 0, True) < fresh
    assert action_probability(player, EventType.PASS, 40, 0, False) < fresh
    assert fatigue(player, 0) == 0 and fatigue(player, 90) == 10
    player.physical.stamina = 30
    assert fatigue(player, 90) == 70
    assert action_probability(player, EventType.PASS, 10, 90, False) < fresh
    player.state.fatigue = 80
    assert fatigue(player, 90) == 100
    player.state.fatigue = 100
    assert fatigue(player, 0) == 100


def test_direct_build_up_generates_longer_passes(clubs):
    distances = {}
    for style in (BuildUpStyle.SHORT, BuildUpStyle.DIRECT):
        home = clubs[0].model_copy(deep=True)
        home.tactical_identity.build_up = style
        values = []
        for seed in range(4):
            match = simulate_match(home, clubs[1], MatchConfig(seed=seed, duration_minutes=20))
            values.extend(
                e.distance
                for e in match.events
                if e.team_id == home.id and e.type == EventType.PASS
            )
        assert len(values) > 20
        distances[style] = mean(values)
    assert distances[BuildUpStyle.DIRECT] > distances[BuildUpStyle.SHORT] + 5


def test_spatial_units_zones_and_shot_geometry():
    start, end = Point(x=0, y=0), Point(x=100, y=100)
    assert math.isclose(distance(start, end), math.hypot(105, 68))
    assert math.isclose(direction(start, end), math.atan2(68, 105))
    assert pitch_zone(start) == 1 and pitch_zone(end) == 18
    assert shot_value(Point(x=90, y=50)) > shot_value(Point(x=60, y=50))
    assert shot_value(Point(x=90, y=50)) > shot_value(Point(x=90, y=5))


@pytest.mark.parametrize("change", ["receiver", "pressure", "links", "time", "zone", "goal"])
def test_corrupt_artifacts_are_rejected(clubs, change):
    result = simulate_match(*clubs)
    if change == "receiver":
        next(e for e in result.events if e.type == EventType.PASS).related_player_id = "missing"
    elif change == "pressure":
        event = next(e for e in result.events if e.under_pressure)
        event.pressured_by = event.player_id
    elif change == "links":
        result.frames[0].possession.event_ids.clear()
    elif change == "time":
        result.frames[0].events[0].minute = 100
    elif change == "zone":
        result.events[0].pitch_zone = 1
    else:
        next(e for e in result.events if e.type == EventType.GOAL).subtype = "from_shot:missing"
    with pytest.raises(ValueError):
        validate_match(result, *clubs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seed": -1},
        {"seed": True},
        {"duration_minutes": 1},
        {"duration_minutes": 91},
        {"duration_minutes": 5.5},
        {"engine_version": "unknown"},
    ],
)
def test_invalid_match_configuration(kwargs):
    with pytest.raises(ValidationError):
        MatchConfig(**kwargs)


def test_invalid_lineups_are_rejected(clubs):
    with pytest.raises(ValueError, match="itself"):
        simulate_match(clubs[0], clubs[0])
    home, away = (club.model_copy(deep=True) for club in clubs)
    home.squad[1].state.suspended = True
    with pytest.raises(ValueError, match="Suspended"):
        simulate_match(home, away)
    bare = generate_league(LeagueConfig(generator_version="league-v1"))
    with pytest.raises(ValueError, match="eleven"):
        simulate_match(*bare.clubs[:2])


def test_cli_json_jsonl_and_manifest(tmp_path):
    config = Path(__file__).resolve().parents[3] / "data/scenarios/match-base.json"
    args = [
        sys.executable,
        "-m",
        "tactix.simulation",
        "--config",
        str(config),
        "--duration-minutes",
        "2",
    ]
    output = tmp_path / "match.json"
    subprocess.run([*args, "--output", str(output)], check=True, capture_output=True, text=True)
    result = MatchResult.model_validate_json(output.read_text(encoding="utf-8"))
    stream = subprocess.run(
        [*args, "--format", "jsonl"], check=True, capture_output=True, text=True
    )
    assert [Event.model_validate_json(line) for line in stream.stdout.splitlines()] == result.events
    failed = subprocess.run([*args, "--output", str(output)], capture_output=True, text=True)
    assert failed.returncode == 2
    assert json.loads(output.read_text(encoding="utf-8"))["match_id"] == result.match_id
    unknown = subprocess.run([*args, "--away", "unknown"], capture_output=True, text=True)
    assert unknown.returncode == 2 and unknown.stdout == ""
