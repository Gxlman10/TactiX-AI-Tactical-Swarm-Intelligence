# Swarm orchestration workflow

`swarm-workflow-v1` (`tactix.workflows`) is the runtime that drives the five-role
swarm end to end, on top of the `swarm-contracts-v1` boundaries ([SWARM.md](SWARM.md))
and the MAF/Foundry specialist adapter ([FOUNDRY.md](FOUNDRY.md)). It turns the
specified handoff order into an executed pipeline and ships a single `MatchReport`.

## Stage order

1. **Fan-out** — Tactical Analyst and Historian run in parallel through MAF/Foundry
   (`run_specialists`), each bounded by timeout, retry and tool budget.
2. **Orchestrator review** — `detect_conflicts` pairs each Analyst finding with one
   same-minute Historian finding as a surfaced *disagreement of cause*: the two frames
   read the same moment through different evidence, and both are shown rather than
   reconciled. Each Historian finding is paired at most once.
3. **Narrator fan-in** — one no-tool language stage turns the findings, conflicts and
   degraded list into a narration whose moments cite their source findings.
4. **Personalizer** — adapts the narration into an analyst and a fan view in the
   requested language. It is skipped and recorded as degraded when no narration exists.
5. **Orchestrator finalize** — deterministic assembly of the `MatchReport`, then a
   re-validation through the frozen Orchestrator boundary so the assembly cannot drift
   from the contract.

Orchestration is deterministic code; the Orchestrator never calls a model. The
model-backed stages are the Analyst/Historian fan-out and the Narrator/Personalizer; the
model only interprets state the lower layers already computed and never counts football
actions. Every model response is re-validated against the domain boundary before it
reaches the report. If the shared state is ever off-contract, the run ships a deterministic
partial report via `fallback_report` instead of raising.

## Degradation

Each stage either completes or degrades (timeout, provider error, or output that fails
boundary validation after the bounded retries). A degraded stage contributes nothing:
its owned field stays empty, its name joins `context.degraded`, and the report ships
with `partial=True`. A degraded Narrator skips the Personalizer. A surfaced conflict is
never erased by a later degraded stage. No stage fabricates substitute success text.

## Running it

Live execution needs a configured Foundry project (see [FOUNDRY.md](FOUNDRY.md)); the
Narrator and Personalizer call the model. From `backend/`:

```sh
uv run python -m tactix.workflows --check-config
uv run --extra agents python -m tactix.workflows --at-second 3720 --language en \
  --output ../data/generated/report-ashford.json
```

The output file must not already exist, and generated files belong in the ignored
`data/generated/` directory. The process exits non-zero when the run ships partial.

## Verification

`uv run pytest tests/unit/test_workflow_orchestration.py -q` exercises the whole
pipeline offline: a deterministic double replaces the Narrator/Personalizer executor,
so conflict surfacing, climax provenance, graceful degradation and the
boundary-validated report assembly are checked without a provider or the `agents`
extra. The MAF/Foundry language stage reuses the specialists' execution contract and is
covered by the live adapter path.
