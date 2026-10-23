"""Offline coverage of the swarm orchestration runtime.

The Narrator/Personalizer executor is replaced with a deterministic double so the whole
pipeline — conflict detection, the fan-in handoff, graceful degradation and the final
boundary-validated report — runs without a Foundry provider or the ``agents`` extra. The
findings, narration and personalization are built to pass the frozen domain boundary, so the
report assembly is checked against the real contract, not a loosened one.
"""

import pytest

from tactix.agents.contracts import NarratorOutput, PersonalizerOutput
from tactix.agents.foundry import AgentExecution, SpecialistRun
from tactix.agents.tools import EvidenceTools
from tactix.config import Settings
from tactix.demo.scenario import build_demo
from tactix.domain.agents import (
    Evidence,
    Finding,
    MatchContext,
    Narration,
    NarrationMoment,
    Personalization,
    PersonalizedView,
)
from tactix.domain.enums import AgentName, Frame, Language, ViewMode
from tactix.workflows.orchestration import StageOutcome, detect_conflicts, run_match_report

AT_SECOND = 3720
MINUTE = AT_SECOND // 60
A, H, N, P = (
    AgentName.TACTICAL_ANALYST,
    AgentName.HISTORIAN,
    AgentName.NARRATOR,
    AgentName.PERSONALIZER,
)


@pytest.fixture(scope="module")
def scope():
    demo = build_demo()
    return EvidenceTools(
        demo.live, demo.league, AT_SECOND, revision=7, historical_matches=demo.historical_matches
    )


def _findings(scope: EvidenceTools) -> tuple[Finding, Finding]:
    live_id = sorted(scope.live_events)[-1]
    fixture_id = sorted(scope.fixtures)[0]
    analyst = Finding(
        id="a-62",
        agent=A,
        moment_minute=MINUTE,
        frame=Frame.TACTICAL,
        claim="Ashford lost the ball in midfield and the line never recovered shape.",
        confidence=0.8,
        evidence=Evidence(event_ids=[live_id], description="Live turnover then concession."),
    )
    historian = Finding(
        id="h-62",
        agent=H,
        moment_minute=MINUTE,
        frame=Frame.HISTORICAL,
        claim="This repeats Ashford's season-long concession after midfield losses.",
        confidence=0.7,
        evidence=Evidence(event_ids=[live_id], description="Same pattern as earlier fixtures."),
        references=[fixture_id],
    )
    return analyst, historian


def _specialist_run(
    scope: EvidenceTools, *, degraded: list[AgentName] | None = None
) -> SpecialistRun:
    analyst, historian = _findings(scope)
    degraded = degraded or []
    context = MatchContext(
        match_id=scope.match_id,
        minute=MINUTE,
        metrics=scope.metrics(),
        analyst_findings=[] if A in degraded else [analyst],
        historian_findings=[] if H in degraded else [historian],
        degraded=list(degraded),
    )
    executions = [
        AgentExecution(
            agent=role,
            status="degraded" if role in degraded else "complete",
            attempts=1,
            elapsed_ms=1,
            tool_calls=[],
            failure="timeout" if role in degraded else None,
        )
        for role in (A, H)
    ]
    return SpecialistRun(
        match_id=scope.match_id,
        at_second=AT_SECOND,
        revision=7,
        context=context,
        executions=executions,
        partial=bool(degraded),
    )


def _narration_from(context: MatchContext) -> Narration:
    """Cite only the findings that actually reached the Narrator, like a grounded model."""
    available = [f.id for f in [*context.analyst_findings, *context.historian_findings]]
    if not available:
        return Narration()
    return Narration(
        play_by_play=[
            NarrationMoment(
                minute=MINUTE,
                text="Ashford gave it away in midfield and conceded moments later.",
                source_finding_ids=available,
            )
        ],
        recap="A concession that fit a familiar Ashford pattern.",
        key_moments=[
            NarrationMoment(
                minute=MINUTE,
                text="The decisive midfield turnover.",
                source_finding_ids=available[:1],
            )
        ],
    )


def _personalization() -> Personalization:
    return Personalization(
        language=Language.EN,
        views=[
            PersonalizedView(mode=ViewMode.ANALYST, language=Language.EN, content="Dense read."),
            PersonalizedView(mode=ViewMode.FAN, language=Language.EN, content="The story."),
        ],
    )


def _runner(*, narrator="ok"):
    """Deterministic stand-in for the MAF language executor."""

    async def run(role, context, scope, settings, preferences, client):
        if role is N:
            if narrator != "ok":
                return None, StageOutcome(agent=N, status="degraded", attempts=1, failure=narrator)
            return NarratorOutput(narration=_narration_from(context)), StageOutcome(
                agent=N, status="complete"
            )
        return PersonalizerOutput(personalization=_personalization()), StageOutcome(
            agent=P, status="complete"
        )

    return run


def _settings() -> Settings:
    return Settings(_env_file=None)


def test_detect_conflicts_pairs_same_minute_findings_once(scope):
    analyst, historian = _findings(scope)
    second_historian = historian.model_copy(update={"id": "h-62b"})
    context = MatchContext(
        match_id=scope.match_id,
        minute=MINUTE,
        analyst_findings=[analyst],
        historian_findings=[historian, second_historian],
    )
    conflicts = detect_conflicts(context)
    assert len(conflicts) == 1
    assert conflicts[0].analyst_finding_id == "a-62"
    assert conflicts[0].historian_finding_id == "h-62"
    assert conflicts[0].moment_minute == MINUTE


def test_detect_conflicts_ignores_findings_at_different_minutes(scope):
    analyst, historian = _findings(scope)
    early = historian.model_copy(update={"id": "h-10", "moment_minute": 10})
    context = MatchContext(
        match_id=scope.match_id,
        minute=MINUTE,
        analyst_findings=[analyst],
        historian_findings=[early],
    )
    assert detect_conflicts(context) == []


async def test_full_pipeline_surfaces_conflict_and_preserves_provenance(scope):
    result = await run_match_report(
        scope,
        _settings(),
        specialists=_specialist_run(scope),
        stage_runner=_runner(),
    )
    assert not result.partial and result.context.degraded == []
    assert [stage.status for stage in result.stages] == ["complete", "complete"]

    # The disagreement of cause is shown, not hidden.
    assert len(result.report.conflicts) == 1
    assert result.report.conflicts[0].analyst_finding_id == "a-62"

    # The climax paragraph keeps the provenance the UI highlights on hover.
    moment = result.report.narration.play_by_play[0]
    assert moment.source_finding_ids == ["a-62", "h-62"]
    assert result.report.personalization is not None
    assert {v.mode for v in result.report.personalization.views} == {
        ViewMode.ANALYST,
        ViewMode.FAN,
    }
    assert result.report.match_id == scope.match_id and result.report.minute == MINUTE


async def test_degraded_narrator_ships_partial_report_and_skips_personalizer(scope):
    result = await run_match_report(
        scope,
        _settings(),
        specialists=_specialist_run(scope),
        stage_runner=_runner(narrator="timeout"),
    )
    assert result.partial
    assert result.context.degraded == [N, P]
    assert result.report.narration is None and result.report.personalization is None
    # A degraded downstream stage never erases the Orchestrator's surfaced conflict.
    assert len(result.report.conflicts) == 1
    assert [stage.status for stage in result.stages] == ["degraded", "skipped"]


def _offcontract_specialist_run(scope: EvidenceTools) -> SpecialistRun:
    """A specialists run whose findings anchor a minute past the visible cut — the kind of
    off-contract state that could reach the workflow via an injected run."""
    analyst, historian = _findings(scope)
    bad = MINUTE + 10
    analyst = analyst.model_copy(update={"moment_minute": bad})
    historian = historian.model_copy(update={"moment_minute": bad})
    context = MatchContext(
        match_id=scope.match_id,
        minute=MINUTE,
        metrics=scope.metrics(),
        analyst_findings=[analyst],
        historian_findings=[historian],
    )
    executions = [
        AgentExecution(
            agent=role, status="complete", attempts=1, elapsed_ms=1, tool_calls=[], failure=None
        )
        for role in (A, H)
    ]
    return SpecialistRun(
        match_id=scope.match_id,
        at_second=AT_SECOND,
        revision=7,
        context=context,
        executions=executions,
        partial=False,
    )


async def test_offcontract_state_ships_partial_report_via_fallback_not_crash(scope):
    # The boundary rejects the assembled report, so the run must fall back to a deterministic
    # partial report rather than raising out of the pipeline.
    result = await run_match_report(
        scope,
        _settings(),
        specialists=_offcontract_specialist_run(scope),
        stage_runner=_runner(),
    )
    assert result.partial and result.report.partial
    assert AgentName.ORCHESTRATOR in result.report.degraded


async def test_upstream_specialist_failure_flows_through_to_partial_report(scope):
    result = await run_match_report(
        scope,
        _settings(),
        specialists=_specialist_run(scope, degraded=[H]),
        stage_runner=_runner(),
    )
    # With no Historian findings there is no cross-frame disagreement to surface.
    assert result.report.conflicts == []
    # The Narrator still runs on the Analyst's findings; the report ships partial and says so.
    assert result.partial and H in result.report.degraded
    assert result.report.narration is not None
