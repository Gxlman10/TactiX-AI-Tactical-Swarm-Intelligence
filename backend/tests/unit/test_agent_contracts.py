"""Executable role, provenance and degradation boundaries without a model runtime."""

import json
import subprocess
import sys

import pytest

from tactix.agents.__main__ import specification
from tactix.agents.boundaries import build_request, fallback_report, validate_output
from tactix.agents.contracts import SPECS, Preferences
from tactix.agents.tools import EvidenceTools
from tactix.demo.scenario import build_demo, demo_context
from tactix.domain.agents import Finding, MatchContext, MatchReport
from tactix.domain.enums import AgentName, Frame, Language
from tactix.domain.metrics import Evidence

A, H, N, P, ORCHESTRATOR = (
    AgentName.TACTICAL_ANALYST,
    AgentName.HISTORIAN,
    AgentName.NARRATOR,
    AgentName.PERSONALIZER,
    AgentName.ORCHESTRATOR,
)


@pytest.fixture(scope="module")
def bundle():
    return build_demo()


@pytest.fixture(scope="module")
def tools(bundle):
    return EvidenceTools(
        bundle.live, bundle.league, 3720, revision=2, historical_matches=bundle.historical_matches
    )


def context(tools):
    return MatchContext(
        match_id=tools.match_id, minute=tools.at_second // 60, metrics=tools.metrics()
    )


def finding(bundle, agent=A):
    data = demo_context(bundle, 3720)
    historical = next(iter(data.historical_patterns))
    return Finding(
        id="analyst-62" if agent == A else "historian-62",
        agent=agent,
        moment_minute=62,
        frame=Frame.TACTICAL if agent == A else Frame.HISTORICAL,
        claim="A visible midfield loss preceded this goal by twenty seconds.",
        confidence=0.8,
        evidence=Evidence(
            description="Loss, recovery, shot and goal.",
            event_ids=data.climax.event_ids
            if agent == A
            else data.historical_patterns[historical][0].event_ids,
        ),
        references=[] if agent == A else [historical],
    )


def populated(tools, bundle):
    state = context(tools)
    state.analyst_findings = [finding(bundle)]
    state.historian_findings = [finding(bundle, H)]
    return state


def narrative():
    return {
        "play_by_play": [
            {
                "minute": 62,
                "text": "Hartley's goal repeats a recorded pattern.",
                "source_finding_ids": ["analyst-62", "historian-62"],
            }
        ],
        "recap": "A midfield turnover led to a goal.",
        "key_moments": [],
    }


def test_five_prompts_schemas_and_role_scoping(tools, bundle):
    spec = specification()
    assert len(spec["agents"]) == 5 and spec["model_execution"] is False
    assert spec["stages"][0] == ["tactical_analyst", "historian"]
    assert all(len(a["prompt_sha256"]) == 64 for a in spec["agents"])
    state = populated(tools, bundle)
    analyst = build_request(A, state, tools)
    historian = build_request(H, state, tools)
    narrator = build_request(N, state, tools)
    assert set(json.loads(analyst["messages"][1]["content"])["inputs"]) == {"metrics"}
    assert "universe" in json.loads(historian["messages"][1]["content"])["inputs"]
    assert not narrator["tools"]
    assert "metrics" not in json.loads(narrator["messages"][1]["content"])["inputs"]
    assert all(len(spec.prompt()) > 1000 for spec in SPECS.values())


def test_valid_handoffs_review_narration_personalization_and_final_report(tools, bundle):
    state = context(tools)
    for agent, field in [(A, "analyst_findings"), (H, "historian_findings")]:
        output = validate_output(
            agent, {"findings": [finding(bundle, agent).model_dump(mode="json")]}, state, tools
        )
        setattr(state, field, output.findings)
    assert (
        validate_output(
            ORCHESTRATOR, {"conflicts": [], "report": None}, state, tools, phase="review"
        ).report
        is None
    )
    state.narration = validate_output(N, {"narration": narrative()}, state, tools).narration
    preferences = Preferences(language=Language.ES)
    request = build_request(P, state, tools, preferences)
    assert (
        json.loads(request["messages"][1]["content"])["inputs"]["preferences"]["language"] == "es"
    )
    payload = {
        "personalization": {
            "language": "es",
            "views": [
                {
                    "mode": "analyst",
                    "language": "es",
                    "content": "Pérdida y gol en veinte segundos.",
                },
                {
                    "mode": "fan",
                    "language": "es",
                    "content": "Hartley marca tras recuperar el balón.",
                },
            ],
        }
    }
    state.personalization = validate_output(P, payload, state, tools, preferences).personalization
    report = MatchReport(
        match_id=state.match_id,
        minute=62,
        narration=state.narration,
        personalization=state.personalization,
    )
    final = validate_output(
        ORCHESTRATOR,
        {"conflicts": [], "report": report.model_dump(mode="json")},
        state,
        tools,
        preferences,
    )
    assert not final.report.partial and final.report.narration == state.narration


def test_tool_counts_and_pattern_evidence_match_demo(tools, bundle):
    data = demo_context(bundle, 3720)
    goals = tools.invoke(H, "player_goals", {"player_id": data.climax.scorer_id})
    assert goals["data"]["goals"] == data.scorer_season_goals == 10
    assert goals["at_second"] == 3720 and goals["revision"] == 2
    patterns = tools.invoke(H, "read_patterns", {"club_id": bundle.live.home_club_id})["data"]
    assert any(bundle.climax_goal_id in p["event_ids"] for p in patterns["live"])
    assert len(patterns["historical"]) == 4
    metrics = tools.invoke(A, "read_metrics", {})["data"]
    metrics["teams"].clear()
    assert len(tools.invoke(A, "read_metrics", {})["data"]["teams"]) == 2


def test_future_events_are_unavailable_even_with_known_authored_ids(bundle):
    before = EvidenceTools(
        bundle.live, bundle.league, 3719, historical_matches=bundle.historical_matches
    )
    for agent in (A, H):
        with pytest.raises(ValueError, match="future"):
            before.invoke(agent, "read_events", {"event_ids": [bundle.climax_goal_id]})
    result = before.invoke(H, "read_patterns", {"club_id": bundle.live.home_club_id})
    assert not any(bundle.climax_goal_id in p["event_ids"] for p in result["data"]["live"])


def test_historian_can_resolve_audited_events_but_analyst_cannot(tools, bundle):
    key = next(iter(tools.historical_events))
    assert tools.invoke(H, "read_events", {"event_ids": [key]})["data"][0]["id"] == key
    with pytest.raises(ValueError, match="unauthorized"):
        tools.invoke(A, "read_events", {"event_ids": [key]})
    for agent in (N, P, ORCHESTRATOR):
        with pytest.raises(PermissionError):
            tools.invoke(agent, "read_events", {"event_ids": [bundle.climax_goal_id]})


@pytest.mark.parametrize(
    "tool,args",
    [
        ("read_metrics", {"invented": True}),
        ("read_events", {"event_ids": []}),
        ("read_events", {"event_ids": ["same", "same"]}),
        ("read_fixtures", {"club_id": "unknown"}),
        ("read_player", {"player_id": "unknown"}),
        ("read_fixtures", {"club_id": "unknown", "limit": 100}),
    ],
)
def test_invalid_tool_arguments_fail_instead_of_silently_truncating(tools, tool, args):
    with pytest.raises(ValueError):
        tools.invoke(H, tool, args)


def test_fixture_queries_and_profile_results_are_bounded_and_isolated(tools, bundle):
    ashford = bundle.live.home_club_id
    fixtures = tools.invoke(H, "read_fixtures", {"club_id": ashford, "limit": 3})["data"]
    assert [f["matchday"] for f in fixtures] == [12, 11, 10]
    assert (
        len(
            tools.invoke(
                H, "read_fixtures", {"club_id": ashford, "fixture_ids": [fixtures[-1]["id"]]}
            )["data"]
        )
        == 1
    )
    with pytest.raises(ValueError):
        tools.invoke(H, "read_fixtures", {"club_id": ashford, "fixture_ids": ["missing"]})
    club = tools.invoke(H, "read_club", {"club_id": ashford})["data"]
    club["squad"].clear()
    assert len(tools.invoke(H, "read_club", {"club_id": ashford})["data"]["squad"]) == 23


@pytest.mark.parametrize(
    "mutation",
    [
        "author",
        "frame",
        "moment",
        "empty_evidence",
        "unknown_event",
        "unknown_fixture",
        "empty_claim",
        "confidence",
        "extra",
        "numeric_string",
    ],
)
def test_invalid_findings_rejected(tools, bundle, mutation):
    payload = finding(bundle).model_dump(mode="json")
    if mutation == "author":
        payload["agent"] = H.value
    elif mutation == "frame":
        payload["frame"] = "historical"
    elif mutation == "moment":
        payload["moment_minute"] = 63
    elif mutation == "empty_evidence":
        payload["evidence"]["event_ids"] = []
    elif mutation == "unknown_event":
        payload["evidence"]["event_ids"] = ["missing"]
    elif mutation == "unknown_fixture":
        payload["references"] = ["missing"]
    elif mutation == "empty_claim":
        payload["claim"] = " "
    elif mutation == "confidence":
        payload["confidence"] = 1.1
    elif mutation == "extra":
        payload["hidden_future"] = "extra"
    else:
        payload["moment_minute"] = "62"
    with pytest.raises(ValueError):
        validate_output(A, {"findings": [payload]}, context(tools), tools)


def test_historical_event_must_cite_its_fixture_and_ids_cannot_repeat(tools, bundle):
    item = finding(bundle, H).model_dump(mode="json")
    item["references"] = []
    with pytest.raises(ValueError, match="fixture"):
        validate_output(H, {"findings": [item]}, context(tools), tools)
    valid = finding(bundle).model_dump(mode="json")
    with pytest.raises(ValueError, match="unique"):
        validate_output(A, {"findings": [valid, valid]}, context(tools), tools)


def test_narration_requires_real_upstream_provenance(tools, bundle):
    state = populated(tools, bundle)
    value = narrative()
    value["play_by_play"][0]["source_finding_ids"] = ["unknown"]
    with pytest.raises(ValueError, match="source"):
        validate_output(N, {"narration": value}, state, tools)
    value = narrative()
    value["play_by_play"][0]["minute"] = 61
    with pytest.raises(ValueError, match="precede"):
        validate_output(N, {"narration": value}, state, tools)
    empty = {"play_by_play": [], "recap": "Invented recap", "key_moments": []}
    with pytest.raises(ValueError, match="sourced"):
        validate_output(N, {"narration": empty}, context(tools), tools)


def test_conflicts_are_anchored_and_cannot_be_hidden(tools, bundle):
    state = populated(tools, bundle)
    conflict = {
        "moment_minute": 62,
        "analyst_finding_id": "analyst-62",
        "historian_finding_id": "historian-62",
        "resolution": "Show both readings.",
    }
    output = validate_output(
        ORCHESTRATOR, {"conflicts": [conflict], "report": None}, state, tools, phase="review"
    )
    state.conflicts = output.conflicts
    with pytest.raises(ValueError, match="hide"):
        validate_output(
            ORCHESTRATOR, {"conflicts": [], "report": None}, state, tools, phase="review"
        )
    conflict["moment_minute"] = 61
    with pytest.raises(ValueError, match="same-moment"):
        validate_output(
            ORCHESTRATOR,
            {"conflicts": [conflict], "report": None},
            populated(tools, bundle),
            tools,
            phase="review",
        )


def test_partial_report_and_fallback_preserve_degradation(tools, bundle):
    state = context(tools)
    state.degraded = [A, H, N, P]
    report = MatchReport(match_id=state.match_id, minute=62, degraded=state.degraded, partial=False)
    with pytest.raises(ValueError, match="degradation"):
        validate_output(
            ORCHESTRATOR, {"conflicts": [], "report": report.model_dump(mode="json")}, state, tools
        )
    report.partial = True
    assert validate_output(
        ORCHESTRATOR, {"conflicts": [], "report": report.model_dump(mode="json")}, state, tools
    ).report.partial
    fallback = fallback_report(state)
    assert fallback.partial and fallback.degraded == [A, H, N, P, ORCHESTRATOR]
    assert fallback_report(state) == fallback
    with pytest.raises(ValueError, match="degraded"):
        build_request(P, state, tools)
    with pytest.raises(ValueError, match="upstream"):
        build_request(P, context(tools), tools)
    with pytest.raises(ValueError, match="degraded"):
        validate_output(A, {"findings": []}, state, tools)


def test_context_cut_metrics_and_preference_consistency(tools, bundle):
    state = context(tools)
    state.minute = 63
    with pytest.raises(ValueError, match="cut"):
        build_request(A, state, tools)
    state = context(tools)
    state.metrics.teams[0].values[0].value += 1
    with pytest.raises(ValueError, match="computed"):
        build_request(A, state, tools)
    with pytest.raises(ValueError, match="favourite"):
        build_request(H, context(tools), tools, Preferences(favourite_club_id="unknown"))
    stale = populated(tools, bundle)
    stale.degraded = [A]
    with pytest.raises(ValueError, match="stale"):
        build_request(N, stale, tools)


def test_personalization_rejects_language_or_view_loss(tools, bundle):
    state = populated(tools, bundle)
    state.narration = validate_output(N, {"narration": narrative()}, state, tools).narration
    payload = {
        "personalization": {
            "language": "es",
            "views": [{"mode": "analyst", "language": "es", "content": "Texto"}],
        }
    }
    with pytest.raises(ValueError, match="two distinct"):
        validate_output(P, payload, state, tools, Preferences(language=Language.ES))


def test_source_inputs_are_copied_and_invalid_history_is_rejected(bundle):
    copied = bundle.model_copy(deep=True)
    tools = EvidenceTools(copied.live, copied.league, 3720)
    copied.live.frames.clear()
    copied.league.clubs[0].name = "mutated"
    assert (
        tools.invoke(H, "read_club", {"club_id": bundle.live.home_club_id})["data"]["name"]
        == "Ashford"
    )
    bad = next(iter(bundle.historical_matches.values())).model_copy(update={"match_id": "wrong"})
    with pytest.raises(ValueError, match="fixture"):
        EvidenceTools(bundle.live, bundle.league, 3720, historical_matches={"wrong": bad})


def test_cli_exports_five_contracts_without_model_execution(tmp_path):
    output = tmp_path / "contracts.json"
    args = [sys.executable, "-m", "tactix.agents", "--output", str(output)]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact == specification()
    assert subprocess.run(args, capture_output=True).returncode != 0
