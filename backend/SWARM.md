# Agent contracts and evidence tools

`swarm-contracts-v1` defines the five specialist boundaries without executing a
language model. It supplies packaged English prompts, tool schemas, scoped model
requests and response guards around the unchanged domain contracts. It requires
no Foundry credentials, agent-framework installation or network access.

The first real runtime adapter is documented in [FOUNDRY.md](FOUNDRY.md): Analyst
and Historian can run through MAF/Foundry once project access is configured. The
full five-role workflow that sequences every handoff is documented in
[WORKFLOW.md](WORKFLOW.md); cloud smoke validation is pending.

## Roles and handoffs

| Specialist | Reads | Writes | Allowed evidence tools |
|---|---|---|---|
| Tactical Analyst | Computed metrics | analyst_findings | read_metrics, read_events (live only) |
| Historian | Metrics and universe references | historian_findings | read_metrics, read_events, read_club, read_player, read_fixtures, player_goals, read_patterns |
| Narrator | Both findings lists, conflicts, degraded | narration | None |
| Personalizer | Narration, preferences, degraded | personalization | None |
| Orchestrator | Shared context, preferences, phase | conflicts; final report | None |

The intended runtime order is Analyst + Historian fan-out, Orchestrator review,
Narrator fan-in, Personalizer, then Orchestrator finalization. Review returns
anchored conflicts and no report; the runtime merges those conflicts before calling
the Narrator. Finalization preserves upstream outputs and reports their failures.
The two Orchestrator phases are invocations of one specialist, not a sixth agent.

This delivery specifies that order; the runtime that executes it lives in
`tactix.workflows` ([WORKFLOW.md](WORKFLOW.md)), which performs the fan-out, code-level
conflict review, Narrator fan-in, Personalizer and deterministic report assembly with
graceful degradation. Foundry deployment, checkpointing and live report SSE remain
separate tasks. Tools and validation are executable today, independently of those
runtimes. A model is never used for counting football actions.

## Scoped request example

```python
from tactix.agents.boundaries import build_request, validate_output
from tactix.agents.contracts import Preferences
from tactix.agents.tools import EvidenceTools
from tactix.domain.agents import MatchContext
from tactix.domain.enums import AgentName, Language

tools = EvidenceTools(result, league, at_second=3720, revision=2,
                      historical_matches=historical_artifacts)
context = MatchContext(match_id=result.match_id, minute=62, metrics=tools.metrics())
preferences = Preferences(language=Language.ES)
request = build_request(AgentName.HISTORIAN, context, tools, preferences)
# The future runtime sends request['messages'] and binds this role's tools only.
validated = validate_output(AgentName.HISTORIAN, response_json, context, tools, preferences)
context.historian_findings = validated.findings
```

Every request includes version, match ID, exact second and revision in its JSON
user message. The system message loads shared rules plus the specialist prompt.
Only the role's declared inputs are serialized: Narrator does not receive raw
metrics, Personalizer does not receive raw findings or event tools. Model output
schemas are provider-neutral JSON Schema; runtime-specific structured-output
adaptation may be needed. They are not a claim of SDK/provider compatibility.

Create one evidence scope per analysis cut, not per event. Frozen MatchContext has
minute precision, so retain the exact second/revision in the runtime envelope and
scope. Before merging a completed call, the future runtime must compare its cut and
revision with the current session and discard obsolete results. That cross-request
concurrency check belongs to the runtime, not these local validation functions.

## Read-only tool contracts

Call `tools.invoke(bound_role, tool_name, arguments)`; the **runtime** binds the
role. A model must never select its own authorization role. Unauthorized tools
raise PermissionError before arguments are inspected. Argument schemas reject extra
fields and numeric coercion. Calls have no filesystem, network or write capability.
Returned values include match ID, cut, revision, tool name and JSON-compatible data.
Calls do not change source snapshots or shared state.

| Tool | Arguments | Result and limits |
|---|---|---|
| read_metrics | {} | Computed advanced-v1 snapshot at the immutable cut |
| read_events | event_ids: 1–50 distinct IDs | Requested visible events, in requested order; any unknown/future/unauthorized ID fails the whole call |
| read_club | club_id | Fictional identity, roster and authored tactical profile |
| read_player | player_id | Recorded attributes/state; no implied live tracking |
| read_fixtures | club_id, optional opponent_id, limit=5 (1–20), optional fixture_ids | Recorded fixtures, newest first; explicit IDs must belong to the query and fit the limit |
| player_goals | player_id | Code-counted historical scorer rows plus visible live GOAL markers, with fixture/live-event sources |
| read_patterns | club_id | Event-backed midfield concessions in supplied historical artifacts and the visible live cut; explicit coverage limitation |

Live future events cannot be retrieved even if their IDs are guessed from the
authored scenario. Historical event lookup is Historian-only. Audited historical
artifacts must match a recorded fixture's IDs, clubs and score, and pass full match
validation. Summary-only fixtures remain useful for score/scorer facts but supply
no invented event stream. Pattern detection requires real loss/recovery/shot/goal
links and marks absent historical artifacts as unknown, not a negative observation.

## Output guards

- Findings require the expected author/frame, a nonempty claim and evidence
  explanation, unique IDs, bounded minute/confidence and available sources.
  Analyst findings require live event IDs and no historical fixture references.
  Historian findings require available event and/or fixture evidence; each audited
  historical event must also cite its owning fixture.
- IDs are globally unique across both findings lists. Unknown nested fields are
  rejected at the boundary even though the frozen domain models otherwise ignore
  extra fields. JSON response parsing rejects numeric strings for numeric fields.
- Narration moments require real upstream source_finding_ids, nonempty text and
  chronology consistent with those sources and the visible cut. A recap requires at
  least one sourced moment. With no findings, an empty narration is valid.
- Personalization preserves the requested language, club and player exactly and
  requires two nonempty views, analyst and fan, in that language. It cannot run
  without narration. English and Spanish are the supported languages.
- Conflicts cite one finding from each specialist at the same minute, with a
  nonempty presentation of both readings. Existing conflicts cannot disappear.
- Final reports preserve match/minute, narration, personalization and the runtime's
  degraded list, with partial equal to whether that list is nonempty. A failed
  producer cannot contribute stale fields. Retrying an agent requires the runtime
  to clear its degraded status first.

These guards validate structure, scope and reference integrity. They **do not prove
the truth of arbitrary prose**, calibrated confidence, genuine semantic conflict,
faithful translation or numerical consistency inside free text. A model can cite
the right ID while misdescribing it. Future evaluations must check factual claims
and transformations against these deterministic sources. Recap and personalized
content have no additional provenance fields in the frozen contract; their source
lineage remains the validated preceding handoffs.

Tool failures and malformed output must be handled by the runtime. A bounded retry
may correct output; after exhaustion, mark the stage degraded and clear its
owned fields rather than generating substitute success text. If supervision itself
fails, `fallback_report(context)` copies available fields into a deterministic
partial report and records the Orchestrator as degraded. It does not fabricate
findings, merge state or hide conflicts. Validate upstream state before using it.

## Export and verification

From `backend/`, export prompts, SHA-256 checksums, role boundaries and schemas:

```powershell
uv run python -m tactix.agents --output ../data/generated/swarm-contracts-v1.json
```

The output file must not exist. The artifact explicitly records model_execution:
false. Prompt or boundary behavior changes require a new published contract version.
Prompts are package resources, so the same instructions can be loaded by a future
runtime adapter without copying inline strings.

`uv run pytest tests/unit/test_agent_contracts.py -q` checks all five handoffs over
the actual Ashford evidence, code-counted player goals, tool permissions, future
event exclusion, malformed outputs, historical ownership, narrative provenance,
conflicts, preferences and partial-report fallback. This is offline contract
verification, not a live model evaluation or proof of deployed orchestration.
