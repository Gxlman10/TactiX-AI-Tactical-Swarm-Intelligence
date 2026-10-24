# Analyst and Historian on MAF + Foundry

`specialists-maf-v1` implements the two-specialist fan-out using real Microsoft
Agent Framework `Agent` and `FunctionTool` objects. The normal provider is
`FoundryChatClient`, with local evidence tools and the existing versioned prompts.
It does not replace unavailable models with scripted football commentary.

**Cloud validation is pending:** this workspace has no configured Foundry project
endpoint/deployment or active Azure CLI login. Offline SDK tests pass, but they are
not evidence that a model deployment is accessible or that live model claims are
factually correct. The associated task stays in review until both specialists pass
a real Foundry smoke run.

## Install and configure

From `backend/`, install the locked agents extra:

```powershell
uv sync --locked --dev --extra agents
uv run --extra agents python -m tactix.agents.live --check-config
```

The extra selects `agent-framework-core==1.19.0` and
`agent-framework-foundry==1.13.1`, plus Azure Identity. Those packages have separate
version lines. The broad all-provider metapackage has been replaced with the
specific connectors this task uses. Base backend functionality does not import
the optional SDK at startup. CI installs the extra and runs the SDK tests.

When a project and model deployment have been chosen, set these values in the
ignored root `.env` or process environment:

```dotenv
TACTIX_FOUNDRY_ENDPOINT=https://RESOURCE.services.ai.azure.com/api/projects/PROJECT
TACTIX_FOUNDRY_MODEL=DEPLOYMENT_NAME
TACTIX_FOUNDRY_AUTHENTICATION=cli
```

`MODEL` is the actual deployment name in that project. The endpoint must be the
HTTPS project endpoint with `/api/projects/PROJECT`, not a portal URL or a
standalone Azure OpenAI resource endpoint. The deployment must support function
tools and structured JSON output. No model/deployment is assumed by the code.
Choosing/provisioning the project and its model remains an external setup step.

For local Entra authentication, run `az login` in the intended tenant/subscription.
The logged-in identity needs inference permission on the project/deployment.
Other explicit modes are `default` (DefaultAzureCredential) and `managed_identity`
(ManagedIdentityCredential). A key in the legacy `TACTIX_FOUNDRY_API_KEY` field is
**not used** by this project-based adapter. An API-key-only resource would require
a separately verified adapter; do not treat that field as a working fallback.

`--check-config` prints only presence flags, package versions, auth mode and
`live_verified:false`. It never retrieves credentials, authenticates, contacts
Foundry or proves authorization. Endpoint/model values and keys are not printed.

## Run the real smoke

```powershell
uv run --extra agents python -m tactix.agents.live --at-second 3720 --output ../data/generated/foundry-62.json
```

The CLI builds the authored Ashford demo, fixes the evidence cut and runs both
specialists concurrently. The output path must be new. Missing configuration
fails before model execution and creates no output. A partial run writes its
diagnostic artifact but exits with code 2. It never writes a fabricated success.

The artifact contains runtime version, match ID, cut, revision, validated
MatchContext and per-specialist execution diagnostics. A complete run requires
both statuses complete and partial=false. An empty findings list is a valid
insufficient-evidence response, not proof the intended demo explanation succeeded.
For live signoff, inspect the findings' claims against cited events and fixtures;
verify that the Historian contributes relevant recorded context. Record the actual
deployment and smoke evidence without publishing credentials or raw provider errors.

## API integration

POST `/api/v1/sessions/{session_id}/analyze` analyzes the session's current integer
clock cut and revision. It returns `SpecialistRun`; it does not run Narrator,
Personalizer or either Orchestrator phase, and does not claim to return MatchReport.
The response includes both findings lists, degraded roles and diagnostic codes.

- 503: missing project/model configuration or agents extra.
- 409: another analysis is active for that session, or seek changed revision before
  or during inference. Results from the obsolete revision are discarded.
- 404: unknown or deleted session, including deletion during inference.
- 200: validated complete or explicitly partial result. Check partial and degraded;
  authentication/provider errors can produce partial=true even with configuration.

Only one analysis per session can run at a time. The shared activation policy in
`tactix.agents.activation` permits an initial cut, a newly observed goal, a material
momentum shift, or a crossed five-minute window; ordinary events only refresh metrics.
Use those triggers rather than every SSE tick. Existing session capacity limits still apply. Request
cancellation propagates into the concurrent model tasks and clears the active flag.
Playback may advance while inference runs; the result always carries its captured
at_second and revision. A completed old cut on the same revision is a historical
analysis, not a claim of being current. The frontend must label or discard it.

## Execution bounds and evidence

Each role receives a separate fresh Agent and request with only its authorized
inputs/tools. The Foundry client is shared only on that event loop; no conversation
session is shared across roles or retries. Tools invoke the existing strict
EvidenceTools implementation. The adapter uses `response_format=FindingsOutput`
and applies the full boundary validator to raw response text before merging.

Defaults, configurable through the `TACTIX_` environment prefix:

| Variable suffix | Default | Bound |
|---|---|---|
| FOUNDRY_TIMEOUT_SECONDS | 30 | >0, <=120; total role budget, including validation retries |
| FOUNDRY_MAX_ATTEMPTS | 2 | 1–2; retry malformed/invalid output only |
| FOUNDRY_MAX_TOOL_CALLS | 8 | 1–20; evidence-access budget across attempts |
| FOUNDRY_MAX_ITERATIONS | 5 | 1–10 model roundtrips per attempt |
| FOUNDRY_MAX_TOKENS | 2048 | 256–8192 output tokens per response |

SDK function-loop limits are combined with a local tool budget checked **before**
evidence access. A parallel batch cannot execute unlimited extra accesses. Traces
retain at most the configured number plus one budget-exceeded marker. Invalid tool
requests return a generic error that the model can correct within the budget.
SDK transport retries are disabled so they do not multiply the app's attempt policy.
Provider failures are not retried by this adapter. Tool usage, roundtrips and output
tokens are bounded; these limits are not a fixed monetary-cost guarantee.

Failure codes are timeout, invalid_output, provider_error, tool_budget and
duplicate_ids. A failed role contributes no findings, and a successful sibling is
preserved. Cross-role ID collisions degrade the later role instead of silently
renaming sources. Raw exceptions, tool arguments and provider payloads are absent
from diagnostic artifacts. Shared state stays at the immutable evidence cut.
Credentials, project pipeline and inference transport are closed by the factory.

## Verification and remaining work

`tests/unit/test_foundry_specialists.py` uses real MAF Agent/FunctionTool/function
invocation layers with a controlled model client. It checks local tool execution,
parallel fan-out, output retries, isolated provider failure, timeouts, hard tool
budget enforcement, cancellation, duplicate IDs, safe configuration, real
FoundryChatClient construction/transport cleanup and stale-revision API rejection.
It sends no inference request to Azure and therefore must not be called a live
Foundry integration test. Run it with `uv run --extra agents pytest
tests/unit/test_foundry_specialists.py -q`.

Remaining: select/access an actual project/deployment, complete the cloud smoke,
evaluate claim correctness and then implement the remaining specialist/workflow
tasks. No Azure resources or paid deployments are provisioned by this code.

Implementation reference: [Microsoft Learn — Microsoft Foundry provider](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/model-providers/microsoft-foundry).
The adapter's signatures were checked against the pinned installed SDK versions.
