"""Authored demo provenance, derived ledgers and clock-bounded API evidence."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tactix.demo.__main__ import DemoManifest
from tactix.demo.evidence import midfield_concessions, seconds
from tactix.demo.scenario import build_demo, demo_context
from tactix.domain.common import Point
from tactix.domain.enums import EventType, Outcome
from tactix.main import app
from tactix.metrics.advanced import advanced_metrics_for_match
from tactix.simulation.engine import simulate_match
from tactix.simulation.validation import validate_match
from tactix.universe.generator import generate_league
from tactix.universe.history import validate_history


@pytest.fixture(scope="module")
def bundle():
    return build_demo()


def test_reproducible_bundle_and_procedural_baseline_unchanged(bundle):
    original = generate_league()
    baseline = simulate_match(original.clubs[0], original.clubs[1])
    assert build_demo().model_dump_json() == bundle.model_dump_json()
    assert generate_league() == original
    assert simulate_match(original.clubs[0], original.clubs[1]) == baseline
    assert bundle.league.id != original.id
    assert bundle.live.match_id != baseline.match_id
    assert not {f.id for f in bundle.league.fixtures} & {f.id for f in original.fixtures}
    assert {p.id for c in bundle.league.clubs for p in c.squad} == {
        p.id for c in original.clubs for p in c.squad
    }

    # Most of the procedural match remains: same football data before the overlay.
    def before(result):
        return [
            e.model_dump(exclude={"id", "match_id", "possession_id", "subtype"})
            for e in result.events
            if seconds(e) < 3600
        ]

    assert before(bundle.live) == before(baseline)
    assert len(bundle.live.events) > 500


def test_all_authored_matches_validate_and_historical_summaries_are_derived(bundle):
    validate_history(bundle.league)
    clubs = {c.id: c for c in bundle.league.clubs}
    for result in [bundle.live, *bundle.historical_matches.values()]:
        validate_match(result, clubs[result.home_club_id], clubs[result.away_club_id])
    assert len(bundle.league.fixtures) == 60 and len(bundle.historical_matches) == 4
    for fixture in bundle.league.fixtures:
        if fixture.id not in bundle.historical_matches:
            continue
        match = bundle.historical_matches[fixture.id]
        assert (fixture.home_goals, fixture.away_goals) == match.score
        assert len(fixture.scorers) == sum(match.score)
        metrics = advanced_metrics_for_match(match)
        home = {v.key: v.value for v in metrics.teams[0].values}
        away = {v.key: v.value for v in metrics.teams[1].values}
        assert (fixture.home_xg, fixture.away_xg) == (home["xg_like"], away["xg_like"])
        assert fixture.home_possession == home["possession_pct"]


def test_last_three_and_earlier_meeting_have_event_backing(bundle):
    context = demo_context(bundle, 3720)
    assert context.verified_consecutive_matches == 4
    assert context.earlier_meeting_fixture_ids
    assert len(context.historical_patterns) == 4
    for key, patterns in context.historical_patterns.items():
        match = bundle.historical_matches[key]
        assert patterns
        for pattern in patterns:
            assert set(pattern.event_ids) <= {e.id for e in match.events}
            assert set(pattern.possession_ids) <= {f.possession.id for f in match.frames}
            assert pattern.elapsed_seconds == 20
    ashford = bundle.live.home_club_id
    recent = sorted(
        [f for f in bundle.league.fixtures if ashford in (f.home_club_id, f.away_club_id)],
        key=lambda f: f.matchday,
    )[-3:]
    assert all(context.historical_patterns[f.id] for f in recent)


def test_climax_cutoff_goal_and_player_count_from_actual_ledgers(bundle):
    before, after = demo_context(bundle, 3719), demo_context(bundle, 3720)
    assert before.climax is None and before.preview is None
    assert before.verified_consecutive_matches == 3
    assert after.climax.goal_second == 3720 and after.climax.loss_second == 3700
    assert after.climax.shot_channel == "left" and after.climax.elapsed_seconds == 20
    assert bundle.climax_goal_id in after.climax.event_ids
    scorer = after.climax.scorer_id
    expected = sum(s.player_id == scorer for f in bundle.league.fixtures for s in f.scorers)
    live_goals = [
        e.id
        for e in bundle.live.events
        if e.type == EventType.GOAL and e.player_id == scorer and seconds(e) <= 3720
    ]
    assert after.scorer_season_goals == expected + len(live_goals)
    assert after.scorer_season_goals == before.scorer_season_goals + 1
    assert after.scorer_live_goal_ids == live_goals
    assert str(after.scorer_season_goals) in after.preview and "62:00" in after.preview


@pytest.mark.parametrize("cutoff", [-1, 5401, 1.5, True])
def test_invalid_evidence_cutoff_rejected(bundle, cutoff):
    with pytest.raises(ValueError, match="cutoff"):
        demo_context(bundle, cutoff)


@pytest.mark.parametrize(
    "mutation",
    [
        "outside_midfield",
        "success",
        "not_recovery",
        "wrong_location",
        "wrong_source",
        "wrong_scorer",
        "late",
    ],
)
def test_pattern_requires_actual_causal_events_not_labels(bundle, mutation):
    match = bundle.live.model_copy(deep=True)
    pattern = demo_context(bundle, 3720).climax
    events = {e.id: e for e in match.events}
    loss, recovery, shot, goal = [events[key] for key in pattern.event_ids]
    if mutation == "outside_midfield":
        loss.start.x = 39.99
    elif mutation == "success":
        loss.outcome = Outcome.SUCCESS
    elif mutation == "not_recovery":
        recovery.type = EventType.KICKOFF
    elif mutation == "wrong_location":
        recovery.start = Point(x=10, y=10)
    elif mutation == "wrong_source":
        goal.subtype = "from_shot:missing"
    elif mutation == "wrong_scorer":
        goal.player_id = "someone-else"
    else:
        shot.second, goal.second = 20, 20
    found = midfield_concessions(match, match.home_club_id)
    assert not any(bundle.climax_goal_id in p.event_ids for p in found)


def test_context_count_changes_when_support_is_removed(bundle):
    changed = bundle.model_copy(deep=True)
    context = demo_context(changed, 3720)
    latest = max(
        [f for f in changed.league.fixtures if f.id in changed.historical_matches],
        key=lambda f: f.matchday,
    )
    del changed.historical_matches[latest.id]
    assert (
        demo_context(changed, 3720).verified_consecutive_matches
        < context.verified_consecutive_matches
    )
    scorer = context.climax.scorer_id
    fixture = next(
        f for f in changed.league.fixtures if any(s.player_id == scorer for s in f.scorers)
    )
    fixture.scorers = [s for s in fixture.scorers if s.player_id != scorer]
    assert demo_context(changed, 3720).scorer_season_goals < context.scorer_season_goals


def test_cli_manifest_export_and_overwrite_protection(bundle, tmp_path):
    config = Path(__file__).resolve().parents[3] / "data/scenarios/ashford-demo.json"
    output = tmp_path / "demo"
    args = [
        sys.executable,
        "-m",
        "tactix.demo",
        "--config",
        str(config),
        "--output-dir",
        str(output),
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads((output / "bundle.json").read_text(encoding="utf-8")) == bundle.model_dump(
        mode="json"
    )
    before = (output / "match.json").read_bytes()
    assert subprocess.run(args, capture_output=True, timeout=20).returncode != 0
    assert (output / "match.json").read_bytes() == before
    with pytest.raises(ValidationError):
        DemoManifest(base_match_seed=7)


def test_demo_api_visible_context_and_historical_artifact_lookup():
    with TestClient(app) as client:
        response = client.post("/api/v1/sessions", json={"scenario": "ashford-demo-v1"})
        assert response.status_code == 201, response.text
        info = response.json()
        assert info["scenario"] == "ashford-demo-v1"
        base = f"/api/v1/sessions/{info['session_id']}"
        before = client.get(base + "/context").json()
        assert before["climax"] is None and before["preview"] is None
        league = client.get(base + "/league").json()
        assert all(
            key in {f["id"] for f in league["fixtures"]} for key in before["historical_patterns"]
        )
        fixture_id = next(iter(before["historical_patterns"]))
        historical = client.get(base + f"/history/{fixture_id}")
        assert historical.status_code == 200 and historical.json()["match_id"] == fixture_id
        assert client.get(base + f"/history/{info['state']['match_id']}").status_code == 404
        client.post(base + "/controls", json={"action": "seek", "second": 3719})
        assert client.get(base + "/context").json()["climax"] is None
        client.post(base + "/controls", json={"action": "seek", "second": 3720})
        after = client.get(base + "/context").json()
        assert after["revision"] == 2 and after["climax"]["goal_second"] == 3720
        metrics = client.get(base + "/metrics?advanced=true").json()
        assert metrics["revision"] == 2 and metrics["at_second"] == 3720
        assert client.get(base + "/metrics?at_second=3721").status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"scenario": "unknown"},
        {"scenario": "ashford-demo-v1", "match": {"duration_minutes": 2}},
        {"scenario": "ashford-demo-v1", "match": {"seed": 7}},
        {"scenario": "ashford-demo-v1", "home": "Northbridge", "away": "Ashford"},
    ],
)
def test_demo_api_rejects_incompatible_configuration(body):
    with TestClient(app) as client:
        assert client.post("/api/v1/sessions", json=body).status_code == 422
        assert app.state.sessions.pending == 0


def test_procedural_session_has_no_demo_context():
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions", json={"match": {"duration_minutes": 2}}).json()[
            "session_id"
        ]
        assert client.get(f"/api/v1/sessions/{sid}/context").status_code == 409
        assert client.get(f"/api/v1/sessions/{sid}/history/unknown").status_code == 404
        assert (
            client.get(f"/api/v1/sessions/{sid}/league").json()
            == client.get("/api/v1/league").json()
        )


async def test_scripted_goal_flows_through_existing_sse_without_future_leak(bundle):
    from tactix.api.sessions import Session

    session = Session(bundle.live, 60, lambda: 1000, demo=bundle)
    session.seek(3700)
    revision, cursor = session.resume_cursor(None)
    stream = session.feed(revision, cursor, release=lambda: None)
    first = json.loads((await anext(stream))["data"])
    assert not any(e["event"]["id"] == bundle.climax_goal_id for e in first["events"])
    session.seek(3720)
    packet = await asyncio.wait_for(anext(stream), 1)
    assert packet["event"] == "reset"
    assert any(
        e["event"]["id"] == bundle.climax_goal_id for e in json.loads(packet["data"])["events"]
    )
    await stream.aclose()
