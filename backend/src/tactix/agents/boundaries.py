"""Build scoped model requests and reject structurally ungrounded handoffs."""

import json

from pydantic import BaseModel

from tactix.agents.contracts import CONTRACT_VERSION, SPECS, Phase, Preferences
from tactix.agents.tools import EvidenceTools
from tactix.domain.agents import MatchContext, MatchReport
from tactix.domain.enums import AgentName, Frame, ViewMode


def _finding(finding, agent, tools):
    expected_frame = Frame.TACTICAL if agent == AgentName.TACTICAL_ANALYST else Frame.HISTORICAL
    if (
        finding.agent != agent
        or finding.frame != expected_frame
        or not finding.id.strip()
        or not finding.claim.strip()
        or not finding.evidence.description.strip()
        or not 0 <= finding.moment_minute <= tools.at_second // 60
    ):
        raise ValueError("Finding author, frame, moment or descriptive fields are invalid")
    ids, references = finding.evidence.event_ids, finding.references
    if len(set(ids)) != len(ids) or len(set(references)) != len(references):
        raise ValueError("Evidence and fixture references must be unique")
    if agent == AgentName.TACTICAL_ANALYST:
        if not ids or references or not set(ids) <= tools.live_events.keys():
            raise ValueError("Analyst findings require visible live event evidence only")
    else:
        if (
            not ids
            and not references
            or not set(references) <= tools.fixtures.keys()
            or not set(ids) <= tools.live_events.keys() | tools.historical_events.keys()
        ):
            raise ValueError("Historian findings require known event or fixture evidence")
        if any(
            tools.historical_owner[key] not in references
            for key in ids
            if key in tools.historical_owner
        ):
            raise ValueError("Historical event evidence must cite its fixture")


def _conflicts(conflicts, context):
    analyst = {f.id: f for f in context.analyst_findings}
    historian = {f.id: f for f in context.historian_findings}
    seen = set()
    for conflict in conflicts:
        a, h = (
            analyst.get(conflict.analyst_finding_id),
            historian.get(conflict.historian_finding_id),
        )
        pair = (conflict.analyst_finding_id, conflict.historian_finding_id)
        if (
            a is None
            or h is None
            or pair in seen
            or not conflict.resolution.strip()
            or a.moment_minute != h.moment_minute
            or conflict.moment_minute != a.moment_minute
        ):
            raise ValueError("Conflicts require unique, same-moment findings from both specialists")
        seen.add(pair)


def _context(context, tools, preferences):
    if context.match_id != tools.match_id or context.minute != tools.at_second // 60:
        raise ValueError("Context does not match the exact evidence cut")
    if context.metrics is not None and context.metrics != tools.metrics():
        raise ValueError("Context metrics must equal the computed evidence snapshot")
    if (
        preferences.favourite_club_id is not None
        and preferences.favourite_club_id not in tools.clubs
    ):
        raise ValueError("Unknown favourite club")
    if preferences.focus_player_id is not None and preferences.focus_player_id not in tools.players:
        raise ValueError("Unknown focus player")
    seen = set()
    for agent, findings in [
        (AgentName.TACTICAL_ANALYST, context.analyst_findings),
        (AgentName.HISTORIAN, context.historian_findings),
    ]:
        if agent in context.degraded and findings:
            raise ValueError("A degraded specialist cannot contribute stale findings")
        for finding in findings:
            _finding(finding, agent, tools)
            if finding.id in seen:
                raise ValueError("Finding IDs must be globally unique")
            seen.add(finding.id)
    if len(set(context.degraded)) != len(context.degraded):
        raise ValueError("Degraded agents must be unique")
    if AgentName.NARRATOR in context.degraded and context.narration is not None:
        raise ValueError("A degraded Narrator cannot contribute stale narration")
    if AgentName.PERSONALIZER in context.degraded and context.personalization is not None:
        raise ValueError("A degraded Personalizer cannot contribute stale views")
    _conflicts(context.conflicts, context)
    if context.narration is not None:
        _narration(context.narration, context, tools)
    if context.personalization is not None:
        _personalization(context.personalization, preferences)


def build_request(
    agent: AgentName,
    context: MatchContext,
    tools: EvidenceTools,
    preferences: Preferences | None = None,
    *,
    phase: Phase = "finalize",
) -> dict:
    preferences = preferences or Preferences()
    _context(context, tools, preferences)
    if agent in context.degraded:
        raise ValueError("A degraded agent must be cleared by the runtime before retrying")
    if phase not in ("review", "finalize"):
        raise ValueError("Unknown orchestration phase")
    if agent in (AgentName.TACTICAL_ANALYST, AgentName.HISTORIAN):
        inputs = {"metrics": tools.metrics().model_dump(mode="json")}
        if agent == AgentName.HISTORIAN:
            inputs["universe"] = {
                "club_ids": sorted(tools.clubs),
                "fixture_ids": sorted(tools.fixtures),
            }
    elif agent == AgentName.NARRATOR:
        inputs = context.model_dump(
            mode="json", include={"analyst_findings", "historian_findings", "conflicts", "degraded"}
        )
    elif agent == AgentName.PERSONALIZER:
        if context.narration is None:
            raise ValueError("Personalizer requires an upstream narration")
        inputs = {
            "narration": context.narration.model_dump(mode="json"),
            "preferences": preferences.model_dump(mode="json"),
            "degraded": [a.value for a in context.degraded],
        }
    else:
        inputs = {
            "context": context.model_dump(mode="json"),
            "phase": phase,
            "preferences": preferences.model_dump(mode="json"),
        }
    data = {
        "contract_version": CONTRACT_VERSION,
        "match_id": tools.match_id,
        "at_second": tools.at_second,
        "revision": tools.revision,
        "inputs": inputs,
    }
    spec = SPECS[agent]
    return {
        "agent": agent.value,
        "messages": [
            {"role": "system", "content": spec.prompt()},
            {"role": "user", "content": json.dumps(data, ensure_ascii=False, allow_nan=False)},
        ],
        "output_schema": spec.output.model_json_schema(),
        "tools": tools.schemas(agent),
    }


def _unknown_fields(raw, parsed):
    """Frozen domain models ignore extra fields; reject them at the model boundary."""
    if isinstance(parsed, BaseModel) and isinstance(raw, dict):
        if not set(raw) <= type(parsed).model_fields.keys():
            raise ValueError("Unknown fields in nested agent output")
        for key, value in raw.items():
            _unknown_fields(value, getattr(parsed, key))
    elif isinstance(parsed, list) and isinstance(raw, list):
        for a, b in zip(raw, parsed, strict=True):
            _unknown_fields(a, b)


def _narration(narration, context, tools):
    findings = {f.id: f for f in [*context.analyst_findings, *context.historian_findings]}
    moments = [*narration.play_by_play, *narration.key_moments]
    if narration.recap.strip() and not moments:
        raise ValueError("A recap requires at least one sourced moment")
    for moment in moments:
        ids = moment.source_finding_ids
        if (
            not moment.text.strip()
            or not ids
            or len(set(ids)) != len(ids)
            or not set(ids) <= findings.keys()
            or not 0 <= moment.minute <= tools.at_second // 60
        ):
            raise ValueError("Narration moments require visible source findings")
        if any(findings[key].moment_minute > moment.minute for key in ids):
            raise ValueError("Narration cannot precede its findings")


def _personalization(personalization, preferences):
    if (
        personalization.language != preferences.language
        or personalization.favourite_club_id != preferences.favourite_club_id
        or personalization.focus_player_id != preferences.focus_player_id
        or len(personalization.views) != 2
        or {view.mode for view in personalization.views} != {ViewMode.ANALYST, ViewMode.FAN}
        or any(
            view.language != preferences.language or not view.content.strip()
            for view in personalization.views
        )
    ):
        raise ValueError("Personalization must preserve preferences and supply two distinct views")


def validate_output(
    agent: AgentName,
    payload: dict | str,
    context: MatchContext,
    tools: EvidenceTools,
    preferences: Preferences | None = None,
    *,
    phase: Phase = "finalize",
) -> BaseModel:
    preferences = preferences or Preferences()
    _context(context, tools, preferences)
    if agent in context.degraded:
        raise ValueError("A degraded agent cannot contribute output")
    text = json.dumps(payload, allow_nan=False) if isinstance(payload, dict) else payload
    parsed = SPECS[agent].output.model_validate_json(text, strict=True)
    _unknown_fields(json.loads(text), parsed)
    if agent in (AgentName.TACTICAL_ANALYST, AgentName.HISTORIAN):
        ids = set()
        existing = {f.id for f in [*context.analyst_findings, *context.historian_findings]}
        for finding in parsed.findings:
            _finding(finding, agent, tools)
            if finding.id in ids or finding.id in existing:
                raise ValueError("Output finding IDs must be new and unique")
            ids.add(finding.id)
    elif agent == AgentName.NARRATOR:
        _narration(parsed.narration, context, tools)
    elif agent == AgentName.PERSONALIZER:
        if context.narration is None:
            raise ValueError("Personalizer requires an upstream narration")
        _personalization(parsed.personalization, preferences)
    else:
        _conflicts(parsed.conflicts, context)
        if any(c not in parsed.conflicts for c in context.conflicts):
            raise ValueError("Orchestrator cannot hide existing conflicts")
        if phase == "review":
            if parsed.report is not None:
                raise ValueError("Review phase must not publish a final report")
        elif phase == "finalize":
            report = parsed.report
            if (
                report is None
                or report.match_id != context.match_id
                or report.minute != context.minute
                or report.degraded != context.degraded
                or report.partial != bool(context.degraded)
                or report.narration != context.narration
                or report.personalization != context.personalization
                or report.conflicts != parsed.conflicts
            ):
                raise ValueError("Final report must preserve shared state and degradation")
            if report.narration is not None:
                _narration(report.narration, context, tools)
            if report.personalization is not None:
                _personalization(report.personalization, preferences)
        else:
            raise ValueError("Unknown orchestration phase")
    return parsed


def fallback_report(context: MatchContext) -> MatchReport:
    """A runtime may use this deterministic partial report if supervision fails."""
    degraded = list(dict.fromkeys([*context.degraded, AgentName.ORCHESTRATOR]))
    return MatchReport(
        match_id=context.match_id,
        minute=context.minute,
        narration=context.narration.model_copy(deep=True) if context.narration else None,
        personalization=context.personalization.model_copy(deep=True)
        if context.personalization
        else None,
        conflicts=[c.model_copy(deep=True) for c in context.conflicts],
        degraded=degraded,
        partial=True,
    )
