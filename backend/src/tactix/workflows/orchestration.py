"""Supervise the full swarm: fan-out specialists, code-level conflict detection, the
Narrator and Personalizer language stages, and final report assembly with graceful
degradation.

Orchestration is deterministic code — the Orchestrator never calls a model. It sequences
the handoffs, surfaces genuine same-moment disagreements between the Analyst and the
Historian rather than hiding them, and ships a report that states which agents degraded.
The model-backed stages are the Analyst/Historian fan-out and the Narrator/Personalizer;
the model only interprets state the lower layers already computed, never counts football
actions, and every claim it makes is validated back against the frozen domain boundary
before it reaches the report. If supervision itself drifts off-contract, the run still
ships a deterministic partial report via ``fallback_report`` rather than raising.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel

from tactix.agents.boundaries import build_request, fallback_report, validate_output
from tactix.agents.contracts import (
    SPECS,
    NarratorOutput,
    OrchestratorOutput,
    PersonalizerOutput,
    Preferences,
)
from tactix.agents.runtime import (
    SpecialistRun,
    apply_invocation_limits,
    run_specialists,
)
from tactix.agents.tools import EvidenceTools
from tactix.config import Settings
from tactix.domain.agents import Conflict, MatchContext, MatchReport
from tactix.domain.enums import AgentName

WORKFLOW_VERSION = "swarm-workflow-v1"
LANGUAGE_STAGES = (AgentName.NARRATOR, AgentName.PERSONALIZER)

# A stage runner invokes one language agent and returns its validated output (or None on a
# degraded run) alongside the outcome record. The real implementation drives MAF/Foundry;
# tests inject a deterministic double so the orchestration logic runs without a provider.
StageRunner = Callable[
    [AgentName, MatchContext, EvidenceTools, Settings, Preferences, object],
    Awaitable[tuple[BaseModel | None, "StageOutcome"]],
]


class StageOutcome(BaseModel):
    agent: AgentName
    status: Literal["complete", "degraded", "skipped"]
    attempts: int = 0
    elapsed_ms: int = 0
    failure: str | None = None


class MatchReportRun(BaseModel):
    """The orchestrated result: the specialists' sub-run kept intact, the language-stage
    outcomes, the fully assembled report and whether the run shipped partial."""

    workflow_version: str = WORKFLOW_VERSION
    match_id: str
    at_second: int
    revision: int
    context: MatchContext
    specialists: SpecialistRun
    stages: list[StageOutcome]
    report: MatchReport
    partial: bool


def detect_conflicts(context: MatchContext) -> list[Conflict]:
    """Pair each Analyst finding with one same-minute Historian finding as a surfaced
    disagreement of cause. The two frames read the same moment through different evidence
    (tactical vs historical); the Orchestrator shows both rather than choosing. Each
    Historian finding is paired at most once so every conflict is a distinct pair."""
    by_minute: dict[int, list] = {}
    for historian in context.historian_findings:
        by_minute.setdefault(historian.moment_minute, []).append(historian)
    paired: set[str] = set()
    conflicts: list[Conflict] = []
    for analyst in context.analyst_findings:
        for historian in by_minute.get(analyst.moment_minute, []):
            if historian.id in paired:
                continue
            conflicts.append(
                Conflict(
                    moment_minute=analyst.moment_minute,
                    analyst_finding_id=analyst.id,
                    historian_finding_id=historian.id,
                    resolution=(
                        f"Both readings of minute {analyst.moment_minute} are shown side by "
                        f"side: the tactical read and the historical read, each with its own "
                        f"evidence, rather than reconciled into one."
                    ),
                )
            )
            paired.add(historian.id)
            break
    return conflicts


def _assemble_report(
    context: MatchContext, scope: EvidenceTools, preferences: Preferences
) -> MatchReport:
    """Build the final report from shared state and validate it against the frozen
    Orchestrator boundary, so the deterministic assembly cannot drift from the contract."""
    report = MatchReport(
        match_id=context.match_id,
        minute=context.minute,
        narration=context.narration,
        personalization=context.personalization,
        conflicts=context.conflicts,
        degraded=list(context.degraded),
        partial=bool(context.degraded),
    )
    output = OrchestratorOutput(conflicts=context.conflicts, report=report)
    validate_output(
        AgentName.ORCHESTRATOR,
        output.model_dump(mode="json"),
        context,
        scope,
        preferences,
        phase="finalize",
    )
    return report


async def _maf_language_stage(
    role: AgentName,
    context: MatchContext,
    scope: EvidenceTools,
    settings: Settings,
    preferences: Preferences,
    client,
) -> tuple[BaseModel | None, StageOutcome]:
    """Run one no-tool language agent through a real MAF Agent with a bounded attempt budget.

    Mirrors the specialists' execution contract: a hard timeout, a small retry budget, and a
    strict boundary re-validation of the model's JSON. On any failure it returns no output and
    a degraded outcome; it never fabricates text on the model's behalf.
    """
    from agent_framework import Agent

    began, attempts, failure, parsed = time.monotonic(), 0, None, None
    try:
        # An off-contract shared state is a degraded handoff, not a crash.
        request = build_request(role, context, scope, preferences)
    except ValueError:
        return None, StageOutcome(
            agent=role,
            status="degraded",
            elapsed_ms=round((time.monotonic() - began) * 1000),
            failure="invalid_output",
        )
    try:
        async with asyncio.timeout(settings.model_timeout_seconds):
            for attempts in range(1, settings.model_max_attempts + 1):
                agent = Agent(
                    client=client,
                    name=role.value,
                    instructions=request["messages"][0]["content"],
                    tools=[],
                )
                message = request["messages"][1]["content"]
                if attempts > 1:
                    message += (
                        "\nThe previous response failed validation. Return only the required "
                        "JSON, citing only the supplied findings."
                    )
                try:
                    response = await agent.run(
                        message,
                        options={
                            "response_format": SPECS[role].output,
                            "max_tokens": settings.model_max_tokens,
                            "store": False,
                        },
                    )
                    parsed = validate_output(role, response.text, context, scope, preferences)
                except ValueError:
                    failure, parsed = "invalid_output", None
                    continue
                except Exception:
                    # Provider exceptions can carry endpoints, payloads or credentials.
                    failure, parsed = "provider_error", None
                    break
                failure = None
                break
    except TimeoutError:
        failure, parsed = "timeout", None
    except Exception:
        failure, parsed = "provider_error", None
    outcome = StageOutcome(
        agent=role,
        status="degraded" if failure else "complete",
        attempts=attempts,
        elapsed_ms=round((time.monotonic() - began) * 1000),
        failure=failure,
    )
    return (None if failure else parsed), outcome


async def _run_stage(
    runner: StageRunner,
    role: AgentName,
    context: MatchContext,
    scope: EvidenceTools,
    settings: Settings,
    preferences: Preferences,
    client,
) -> tuple[BaseModel | None, StageOutcome]:
    """Invoke a stage runner, turning any unexpected error into a degraded outcome so one
    stage can never crash the whole run. Cancellation (BaseException) still propagates."""
    try:
        return await runner(role, context, scope, settings, preferences, client)
    except Exception:
        return None, StageOutcome(agent=role, status="degraded", failure="provider_error")


async def run_match_report(
    scope: EvidenceTools,
    settings: Settings,
    preferences: Preferences | None = None,
    *,
    client=None,
    specialists: SpecialistRun | None = None,
    stage_runner: StageRunner | None = None,
) -> MatchReportRun:
    """Drive the whole swarm to a final report.

    ``specialists`` can be supplied to reuse a completed fan-out; ``stage_runner`` overrides
    the Narrator/Personalizer executor. When both are supplied no model provider is ever
    constructed, which is what lets the orchestration be tested offline.
    """
    preferences = preferences or Preferences()
    runner = stage_runner or _maf_language_stage
    needs_provider = client is None and (specialists is None or stage_runner is None)
    if needs_provider:
        from tactix.agents.providers import get_provider

        async with get_provider(settings).client(settings) as resolved:
            return await run_match_report(
                scope,
                settings,
                preferences,
                client=resolved,
                specialists=specialists,
                stage_runner=stage_runner,
            )
    if client is not None:
        apply_invocation_limits(client, settings)

    run = specialists or await run_specialists(scope, settings, client=client)
    context = run.context.model_copy(deep=True)

    # Orchestrator, review phase: surface genuine same-moment disagreements (deterministic).
    context.conflicts = detect_conflicts(context)

    stages: list[StageOutcome] = []

    # Narrator fan-in. With no findings at all the stage still runs and returns an empty
    # narration; it only degrades on timeout, provider error or an ungrounded response.
    narration_out, narrator_outcome = await _run_stage(
        runner, AgentName.NARRATOR, context, scope, settings, preferences, client
    )
    stages.append(narrator_outcome)
    if narrator_outcome.status == "complete" and isinstance(narration_out, NarratorOutput):
        context.narration = narration_out.narration
    else:
        context.degraded.append(AgentName.NARRATOR)

    # Personalizer. It cannot run without an upstream narration, so a degraded Narrator
    # skips it and records the degradation rather than inventing replacement text.
    if context.narration is not None:
        personalized_out, personalizer_outcome = await _run_stage(
            runner, AgentName.PERSONALIZER, context, scope, settings, preferences, client
        )
        stages.append(personalizer_outcome)
        if personalizer_outcome.status == "complete" and isinstance(
            personalized_out, PersonalizerOutput
        ):
            context.personalization = personalized_out.personalization
        else:
            context.degraded.append(AgentName.PERSONALIZER)
    else:
        stages.append(StageOutcome(agent=AgentName.PERSONALIZER, status="skipped"))
        context.degraded.append(AgentName.PERSONALIZER)

    # Orchestrator, finalize phase: assemble and boundary-check the shipped report. If the
    # shared state is off-contract (e.g. an injected specialists run that never passed through
    # run_specialists), ship a deterministic partial report instead of raising.
    try:
        report = _assemble_report(context, scope, preferences)
    except ValueError:
        report = fallback_report(context)
        context.degraded = list(report.degraded)
    return MatchReportRun(
        match_id=scope.match_id,
        at_second=scope.at_second,
        revision=scope.revision,
        context=context,
        specialists=run,
        stages=stages,
        report=report,
        partial=report.partial,
    )
