# TactiX — Tactical Swarm Intelligence

**Understand a football moment through its actions, tactical metrics and season history.**

[![CI](https://github.com/Gxlman10/TactiX-AI-Tactical-Swarm-Intelligence/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/Gxlman10/TactiX-AI-Tactical-Swarm-Intelligence/actions/workflows/ci.yml)

Built for the **Microsoft × Premier League Inside the Game Hackathon 2026**, targeting **Best Multi-Agent System**.

TactiX connects a replayable synthetic match to an evidence explorer and a specialist agent workflow. Inspect the actions behind a metric, follow a transition across the pitch, and compare it with previous fixtures.

## What works today

| Available | What to inspect |
|---|---|
| Reproducible match | Ashford vs Northbridge, with an authored climax at 62:00 |
| Analyst workspace | Advanced metrics, directed pass networks, shot map and historical pattern ledger |
| Evidence trail | Definition → source actions → pitch → match, possession, revision and cutoff IDs |
| Viewer controls | EN/ES interface, Analyst/Fan views, favourite club and player focus |
| Resilient replay | Server clock, pause/seek/speed, SSE cursor recovery and terminal session handling |
| Verified fallback | Full 649-event match, four historical artifacts and nine checkpoints |

**Live model validation is pending.** The MAF/Foundry adapters and full workflow are implemented and tested offline. Recorded context is an authored deterministic preview, not an agent response. Without Foundry configuration, **Analyze match returns 503** while replay and metrics remain usable. The single-agent baseline has a request builder; no live comparison result is claimed.

## Run the studio

Prerequisites: **Node 24**, **uv** and **Python 3.12**. The deterministic demo needs no PostgreSQL, Azure credentials or model.

First terminal:

```sh
git clone --branch dev https://github.com/Gxlman10/TactiX-AI-Tactical-Swarm-Intelligence.git
cd TactiX-AI-Tactical-Swarm-Intelligence/backend
uv sync --locked --dev --extra agents
uv run --locked --extra agents uvicorn tactix.main:app --host 127.0.0.1 --port 8000
```

Second terminal, from the checkout root:

```sh
cd frontend
npm ci
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173), then **Enter the studio → Create demo session**. Keep `VITE_API_BASE` unset: the development proxy forwards `/api` to port 8000. **Open local rehearsal** explicitly selects a shorter exported clip; it never silently replaces a failed server connection.

Locked installation, production build and the browser journey pass in clean Linux CI. Backend setup and PostgreSQL also pass in a clean Windows export. The local Windows frontend install received registry 403 responses and is **not** certified by that run. See [verification](VERIFICATION.md) and the [QA record](docs/QA-2026-10-24.md).

## A two-minute walkthrough

1. Create the demo at **61:00**. Play briefly and pause; the server owns the clock.
2. Choose **Revisit 62:00**: Hartley scores, the score becomes **1–1**, and recorded context links the goal to a midfield loss **20 seconds** earlier.
3. Focus the clock and press Left once. At **61:59**, the score is **1–0** and the current climax is hidden. Return to 62:00.
4. In **Evidence lab**, inspect a metric or pass connection. Its definition and source actions open alongside a pitch view. The analysis cut stays pinned until released or reset by a seek.
5. Open **Pattern ledger → Matchday 6**. Its four historical source actions do not change the live match clock.
6. Switch **Fan/Analyst** and **EN/ES**. The cutoff is retained; club/player controls change the viewer's focus.

Three recent historical Ashford appearances plus this match make **four consecutive verified appearances** of the pattern. The older Northbridge meeting is additional evidence, not another consecutive prior match. Hartley has **ten recorded season goals** at 62:00. The full match ends **2–2**, beyond the short rehearsal clip.

## How the specialists collaborate

Code generates the league/events, computes metrics and freezes the evidence at a revision and cutoff. Models interpret that evidence; they never count football actions.

| Role | Responsibility | Execution |
|---|---|---|
| Tactical Analyst | Tactical patterns supported by computed metrics | MAF/Foundry with scoped evidence tools |
| Historian | Season history, previous fixtures and player context | MAF/Foundry with scoped history tools |
| Orchestrator | Review conflicting frames, coordinate stages and validate the report | Deterministic code |
| Narrator | Match narration citing source finding IDs | Bounded Foundry stage |
| Personalizer | Analyst/fan variants under requested preferences | Bounded Foundry stage |

Analyst and Historian run concurrently. Orchestrator review precedes Narrator fan-in, then Personalizer and final report validation. A degraded Narrator skips Personalizer; failures and conflicts remain visible in a partial report.

Playback SSE carries events and clock updates. Model analysis is an explicit request. A separate activation policy exists for meaningful windows; an automatic live inference scheduler is not claimed. Live provenance and personalization still need a model smoke run.

See [workflow stages](backend/WORKFLOW.md), [agent boundaries](backend/SWARM.md) and [Foundry integration](backend/FOUNDRY.md).

## Optional live inference

Install the agents extra as above. Configure an authorized Foundry project endpoint and deployment name in the ignored root `.env` or environment:

```dotenv
TACTIX_FOUNDRY_ENDPOINT=https://RESOURCE.services.ai.azure.com/api/projects/PROJECT
TACTIX_FOUNDRY_MODEL=DEPLOYMENT_NAME
TACTIX_FOUNDRY_AUTHENTICATION=cli
```

Authenticate with `az login` in the intended subscription. The adapter uses Entra authentication; its legacy API-key field is not a fallback. A project with no model quota cannot run inference.

From `backend/`, inspect readiness without contacting a model:

```sh
uv run --locked --extra agents python -m tactix.workflows --check-config
```

Presence flags and `live_verified:false` are diagnostics, not proof of authorization. Once the deployment is available:

```sh
uv run --locked --extra agents python -m tactix.workflows --at-second 3720 --language en --output ../data/generated/report-ashford.json
```

The output path must be new. Partial runs exit nonzero. This live command has **not** been signed off against an accessible deployment; follow the [real smoke requirements](backend/FOUNDRY.md#run-the-real-smoke).

## Verify a checkout

From `backend/`:

```sh
uv run --locked --extra agents ruff check .
uv run --locked --extra agents pytest -q
uv run --locked --extra agents python -m tactix.demo.recording verify ../data/recordings/ashford-demo-v1 --regenerate
```

PostgreSQL tests require a dedicated `TACTIX_TEST_DATABASE_URL`; otherwise they are skipped. See [migration and persistence checks](VERIFICATION.md#backend-and-postgresql).

From `frontend/`:

```sh
npm run lint
npm test -- --maxWorkers=2
node node_modules/@playwright/test/cli.js install chromium
npm run test:e2e
```

The browser command type-checks the app/tests, builds production assets, starts owned local servers and runs **eight desktop/mobile cases**. It checks cutoffs, evidence, modes/languages, offline recovery and session replacement. It cleans up sessions/processes and retains failure diagnostics. Linux browser system dependencies are covered in [the procedure](VERIFICATION.md#automated-browser-journey).

[CI](https://github.com/Gxlman10/TactiX-AI-Tactical-Swarm-Intelligence/actions/workflows/ci.yml) checks frontend, backend/PostgreSQL, browser tests and Windows recording portability. The [QA baseline](VERIFICATION.md#qa-evidence-and-current-limits) has **352 backend**, **66 frontend unit/component** and **eight e2e** tests. Rebuild with the intended production API URL before deploying: the e2e build targets a loopback test API.

## Deployment and documentation

The backend is deployed to Azure Container Apps with PostgreSQL Flexible Server. Its [health endpoint](https://tactix-backend.blackcliff-8260e62c.brazilsouth.azurecontainerapps.io/health) is separate from model readiness. The frontend has a Vite/nginx container recipe. Public frontend hosting, Foundry signoff and complete deployment automation remain separate delivery gates; no public frontend URL or uptime guarantee is claimed here.

| Topic | Guide |
|---|---|
| Frontend and browser diagnostics | [Frontend](frontend/README.md) |
| REST sessions, controls, metrics and SSE | [API](backend/API.md) |
| Authored scenario and causal evidence | [Demo](backend/DEMO.md) |
| Full offline recording | [Recording](data/recordings/ashford-demo-v1/README.md) |
| Synthetic league and historical ledger | [Universe](backend/UNIVERSE.md), [history](backend/HISTORY.md) |
| Computed metrics | [Core](backend/METRICS.md), [advanced](backend/ADVANCED_METRICS.md) |
| Azure configuration | [Deployment](infra/DEPLOY.md) |

## Scope and integrity

- Clubs, rosters, fixtures and events are fictional. There is no real match data or footage. Homepage athletes are generated artwork, not roster identities. The competition logo identifies the hackathon context, not a fictional club.
- The Ashford climax is an authored, event-backed overlay, not an emergent discovery or live model output.
- Synthetic xG is an uncalibrated proxy. Pitch views show recorded actions and observed pass locations, not continuous tracking.
- Sessions are shared, temporary and held in one worker's memory. Backend restarts invalidate them; replay needs no persisted database state.
- Keep credentials, `.env` and generated live outputs out of Git. The hash-verified recording is a deliberate exception to routine generated-data exclusion.

**License:** [MIT](LICENSE). **Team:** TactiX, Microsoft × Premier League Hackathon 2026.
