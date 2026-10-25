# Verify the demo

This procedure checks the synthetic match and evidence workflow without model credentials.
It does **not** certify live swarm inference, a live baseline comparison or public frontend
hosting. Those require separate deployment and Foundry checks.

Use Node 24, uv and Python 3.12. Start from a fresh checkout, without copying `.env`, `.venv`
or `node_modules` from another workspace. The lockfiles supply dependency versions.

## Automated browser journey

From `backend/`:

```sh
uv sync --locked --dev --extra agents
uv run --locked --extra agents ruff check .
```

From `frontend/`:

```sh
npm ci
node node_modules/@playwright/test/cli.js install chromium
npm run lint
npm test -- --maxWorkers=2
npm run test:e2e
```

The browser command type-checks tests and app, builds Vite, and starts its own backend and
preview servers on loopback ports **8018** and **4178**. Both ports must be free. No database
or external inference is used by this flow. On Linux, install browser system dependencies
with `node node_modules/@playwright/test/cli.js install --with-deps chromium` as CI does.

Expected: **66 component/unit tests** and **eight browser cases** pass. The browser cases run
in desktop and mobile Chromium, using a new context per test and deleting their own sessions.
The runner stops its servers and retains failure traces/video/screenshots in ignored output
directories. See [browser diagnostics](frontend/README.md#browser-demo-regression-suite).

The e2e build points at a local test API. Before deploying static output, rebuild with the
intended production `VITE_API_BASE`; do not publish the loopback e2e build.

## Backend and PostgreSQL

From `backend/`:

```sh
uv run --locked --extra agents pytest -q
uv run --locked --extra agents python -m tactix.demo.recording verify ../data/recordings/ashford-demo-v1 --regenerate
uv run --locked --extra agents python -m tactix.agents.live --check-config
```

Without `TACTIX_TEST_DATABASE_URL`, PostgreSQL tests are skipped. To include them, use a
**dedicated test database**, not a shared or production database. The tests create and drop
isolated schemas. Set the URL in the shell (PowerShell example):

```powershell
$env:TACTIX_TEST_DATABASE_URL='postgresql+psycopg://<user>:<password>@127.0.0.1:<port>/<test_database>'
uv run --locked --extra agents pytest -q
```

To verify migrations separately, point `TACTIX_DATABASE_URL` at that disposable database:

```powershell
$env:TACTIX_DATABASE_URL=$env:TACTIX_TEST_DATABASE_URL
uv run --locked --extra agents alembic upgrade head
uv run --locked --extra agents alembic downgrade base
uv run --locked --extra agents alembic upgrade head
uv run --locked --extra agents alembic current
uv run --locked --extra agents python -m tactix.persistence.demo
```

Expected migration head: `2748aae5c5a6`. The demo stores and retrieves the same league,
club and player. The recording verifies its original hash and event-derived checkpoints.
Regeneration permits only negligible libm differences in event angles (absolute 1e-14 radians);
coordinates, identities, outcomes and all other fields must match exactly.

## Two-minute reviewer path

Use the browser suite above for automation, or start the backend with
`uv run --locked --extra agents uvicorn tactix.main:app --host 127.0.0.1 --port 8000`
and the frontend with `npm run dev` in a second terminal. Its development proxy targets 8000
when no `VITE_API_BASE` is set.

| Action | Expected evidence |
|---|---|
| Open the homepage and enter the studio | Real connection controls; local rehearsal is an explicit choice |
| Create demo, play briefly, then pause | Server clock advances from 61:00; pause retains the cut |
| Revisit 62:00 | 1–1, Hartley goal and authored historical preview |
| Focus the clock and press Left once | 61:59, 1–0, no current climax or future goal |
| Revisit 62:00 and inspect a metric | Backend definition and source actions resolve |
| Open Pattern ledger, select Matchday 6 | Four historical source actions; live cut remains unchanged |
| Switch Fan/Analyst and EN/ES | Same clock and selection; labels/view change |
| Disconnect/reconnect the browser | Last confirmed cut retained; controls disabled until recovery |
| Delete the owned session | Terminal state offers a new demo; no endless automatic retry |

Do not use the narrative preview as evidence that an agent ran. At 62:00, the context contains
the 20-second loss-to-goal chain, three recent historical appearances plus the live match,
and an older Northbridge meeting. Four historical artifacts are not four consecutive prior
matches. The recorded full match has 649 events and ends 2–2.

## Unconfigured model behavior

With no Foundry endpoint/deployment, the safe config diagnostic reports
`endpoint_configured=false`, `deployment_configured=false`, `live_verified=false`.
An Analyze request must return HTTP **503**, with configuration guidance and no fabricated
report. The replay clock, score, revision and deterministic metrics must remain usable.
Never add credentials to the repository or call the live smoke against an unknown deployment.

## QA evidence and current limits

The [QA record](docs/QA-2026-10-24.md) distinguishes local clean-export results from Linux CI,
including a local npm registry restriction. CI runs clean installs, backend/PostgreSQL tests,
frontend checks and the browser journey; Windows CI separately checks recording portability.
See the linked run for the exact revision rather than assuming a green run covers later changes.
