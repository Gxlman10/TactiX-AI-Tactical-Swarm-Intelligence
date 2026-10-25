# TactiX match studio

An interactive studio connected to the synthetic match API over HTTP and SSE, with an explicit offline rehearsal. Built with React, strict TypeScript, Vite, Zustand and react-i18next. All clubs, players and events are fictional.

## Run

Use Node.js 24 (CI uses the same major version) and npm:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The default screen offers a real server session; it does not silently fall back to fixture data. For offline use, choose **Open local rehearsal** or open `/?source=local` (no backend or Azure credentials required).

To connect to the deployed backend in PowerShell, run this in `frontend/`:

```powershell
$env:VITE_API_BASE='https://tactix-backend.blackcliff-8260e62c.brazilsouth.azurecontainerapps.io'
npm run dev -- --port 5174
```

This flow was exercised against Azure, including creation, seek, SSE and metrics. Alternatively copy `.env.example` to `.env.local` and set the same public origin. Restart Vite after changing it. Without a value, the development `/api` proxy targets `http://127.0.0.1:8000`. `VITE_API_BASE` must omit `/api/v1`; it is embedded at build time, including production builds. It is public configuration, never a place for credentials.

### Production container

Build and run the static frontend with the deployed API origin:

```sh
docker build --build-arg VITE_API_BASE=https://your-backend.example.com -t tactix-frontend ./frontend
docker run --rm -p 8080:80 tactix-frontend
```

The image serves the Vite bundle with an SPA fallback and exposes `/health`. For a deployed
frontend origin, configure the backend with `TACTIX_CORS_ORIGINS=https://your-frontend.example.com`
(multiple origins are comma-separated). The container has no credentials; `VITE_API_BASE` is
public build-time configuration.

## Server session behavior

Create an authored Ashford session (starts paused at 61:00) or paste a session UUID to join a shared match. Play, pause, speed and seek are server controls: all viewers follow the same clock. The full 90 minute timeline is available at 1×, 4×, 12× or 60×. The timeline initially renders the 50 latest visible actions; **Show earlier actions** adds 50 more without discarding retained history. Selection is local to the viewer. The pitch follows incoming actions until you select an earlier event; seeking resumes following.

The client rebuilds visible history in pages of up to 500 events and deduplicates overlap by sequence within the session/revision. A seek clears old events, metrics and context immediately. Delayed responses from older revisions are discarded. Metrics are fetched once per second without overlapping requests, plus explicit reconstruction after seek/reconnect, and mapped by team ID. Missing values show a dash. Clock and score always come from the backend; the local timer never runs in server mode.

On stream failure the client retains the last confirmed view and selected action, disables clock controls and shows a retry countdown. Delays grow from 5 to 10, 20 and at most 30 seconds; server Retry-After or SSE retry hints can lengthen that delay. Reconnect is available immediately, with only one recovery in flight. Recovery reads the bounded session state, reconstructs paginated history and resumes from a validated session/revision cursor using the Last-Event-ID header. A changed revision or HTTP 409 discards that cursor and reconstructs without it. HTTP 404 is terminal and offers a new demo or the local rehearsal. Finished matches close their stream; Play seeks to zero and starts again.

Switching to the local rehearsal or unmounting cancels the subscription and pending reads. Sessions created by the view are deleted; joined sessions are left intact. Page exit also attempts a keepalive deletion. Abrupt browser/network failure can prevent cleanup: the current backend has no automatic session expiry and stores sessions in one worker's memory. Restarting the backend invalidates session IDs.

Context remains a labelled authored preview. This integration does not invoke Foundry, Narrator or Personalizer.

```sh
npm run lint
npm test
npm run build
npm run preview
```

The production output is in `dist/`. CI runs a clean install, lint, tests and the production build for every push to `dev` and every pull request.

## Explore the offline rehearsal

- Switch between English and Spanish or Analyst and Fan. Language and mode persist in local storage; the selected event stays intact when switching. Fan hides the metric strip; a complete fan narrative is a later integration.
- Play or pause the 61:00–63:00 clip at 1×, 4× or 12×. The slider also supports arrow keys. Playback stops at the end; Play then restarts the clip.
- Select a visible timeline action with a click, Tab/Enter or Space. Inspect its actor, coordinates, outcome, event ID and possession ID.
- The pitch shows recorded actions from the selected possession, not continuous player tracking. Coordinates are normalized to 0–100; away actions are mirrored on both axes to maintain a fixed home orientation.
- Rewind before 62:00: the goal, its score increment and the historical preview disappear. Future events stay hidden. At 62:00 the score is 1–1; the full source match eventually ends 2–2 outside this clip.

The context panel is explicitly labelled as a scripted preview. Neither a live SSE connection nor agent/model inference is active. Synthetic xG is an uncalibrated deterministic proxy, not a trained probability model.

When connected to the backend, **Analyze match** calls `POST /api/v1/sessions/{session_id}/analyze` and renders the Narrator's source-finding provenance. This requires the backend's Microsoft Foundry project, deployment and Entra authentication to be configured. Without Foundry, the UI and tests can be validated with fixtures, but a live agent smoke test remains pending.

## Data and structure

`src/features/match/fixture.json` contains 12 events and 121 metric cuts exported from the backend's validated `ashford-demo-v1`. Metric cuts are computed by backend code, never by a model or browser narrative. To regenerate from the repository root:

```sh
cd backend
uv run --extra agents python ../frontend/scripts/export-mock.py
```

Review and commit the changed fixture when the source demo changes. Exporting does not require PostgreSQL or Foundry.

- `src/features/match/`: fixture, coordinate/cut selectors, SVG pitch and domain tests.
- `src/features/preferences/`: Zustand playback state and validated persisted preferences.
- `src/App.tsx`: studio layout, timeline, evidence and authored context.
- `src/i18n.ts`: English and Spanish interface strings.
- `src/App.test.tsx`: interaction, language and future-event visibility tests.
- `src/features/live/`: typed API client, session lifecycle/SSE controller, connection panel and integration tests.
- `src/Experience.tsx`: explicit source selection and subscription to the live controller.

The shell includes loading, error, empty and unknown-route states, keyboard controls, visible focus and reduced-motion handling. Server mode uses the API; offline mode makes no API requests. Tests cover resets, stale replies, paginated history, overlapping SSE delivery, reconnect, rejected controls and resource ownership.

## Evidence lab (Analyst mode)

Connect a backend session and open **Evidence lab**. Eight advanced metrics link directly to their backend definitions and source events. Inspect all remaining metrics in the metrics table. Missing values remain distinct from zero; incomplete evidence coverage is reported without rewriting the backend value.

Explore the directed pass network in **Topology** for readable connections or **Observed positions** for spatial interpretation. The circular layout is explicitly non-spatial; observed positions are pass send/receive means, never player tracking. Curved arrows separate reciprocal connections, link thickness encodes completed passes and node size encodes pass observations. Both SVG targets and ranked lists support keyboard selection. The shot map shows SHOT events once, sizes markers by synthetic xG and distinguishes goals with diamonds. Synthetic xG remains an uncalibrated proxy.

Selecting a metric, connection, player, shot or pattern pins its metric cut while playback can continue. **Return to latest cut** releases it; seeking or resetting the session starts a new revision and clears the inspection. Source actions open an inspection pitch and current-match actions also select the main pitch. Provenance includes session, match, revision, cutoff, possession and event IDs.

The pattern ledger separates historical occurrences from the verified consecutive-match count. Historical sources are loaded from that session's fixture artifact and normalized from frame events. They keep their own teams and match identity, without changing the live clock. Switching selection cancels the request, and late replies cannot populate another revision. Current patterns and evidence remain hidden until their cutoff. The offline 12-event rehearsal explicitly has no advanced snapshot; it does not fabricate these views. No Foundry inference is invoked.

Run the contract smoke against a running backend (Node 24):

```sh
node scripts/smoke-analyst.mjs http://127.0.0.1:8000
```

This creates and deletes its own synthetic session, checks cuts immediately before and at 62:00, reconciles metric IDs, directed pass counts, node observations and shot coordinates/xG with source events, and resolves historical pattern evidence from fixture frames. It was also run successfully against the deployed Azure backend. Component tests cover pinned cuts, keyboard inspection, missing/zero values, historical cancellation, revision resets, future-data exclusion and spatial versus topological layouts.

## Connection recovery

`src/features/live/stream.ts` uses streaming fetch so retries can send Last-Event-ID explicitly and inspect HTTP status/Retry-After, which native EventSource does not expose. It accepts UTF-8 fragmented LF/CRLF SSE frames, multiline data and heartbeat comments; incomplete frames are never dispatched. It rejects unexpected content types and oversized frames. LiveSession owns retries, deduplicates sequence numbers, reconciles revisions and aborts the reader on leave. Custom API origins must allow the Last-Event-ID CORS request header (the backend CORS middleware allows request headers).

Reconnecting keeps the server-owned clock untouched: another viewer may continue playback. The UI labels its retained view as stale until reconstruction succeeds. Metrics polling stops with the disconnected stream. Recovery attempts are bounded by the HTTP read timeout and serialized. A seek invalidates the narrative report and late analysis replies cannot populate another revision. No automatic retry of POST analysis or playback controls is performed.

Tests cover transport framing, cursor headers, 404/409/503, Retry-After/SSE retry, EOF, disposal, revision changes, retained data, increasing retry delays, terminal sessions, delayed analysis and EN/ES recovery controls. This does not provide durable sessions: a backend restart still requires a new demo session.

## Editorial homepage

The connection screen now sits inside a concise bilingual introduction: purpose, specialist roles, the evidence-backed Ashford moment and the match studio entry. The existing server/local workflows are unchanged; the TactiX brand link returns to the homepage. The studio shares the midnight blue palette while retaining semantic evidence colors.

The supplied competition logo is displayed as hackathon context, not as a fictional club badge. `public/images/tactix-athletes.webp` is an original generated editorial asset featuring fictional, unbranded athletes; the portraits do not identify roster players. It is compressed to WebP for delivery. No real-player imagery from the visual reference is used. Homepage moment counts come from the exported backend fixture. Agent descriptions explain the architecture and explicitly state that live narration needs a configured model.

Navigation has a mobile menu, visible keyboard focus, section anchors and a skip link. Motion respects reduced-motion preferences. The primary action leads to the real connection panel, with loading/errors and local rehearsal still available.

## Browser demo regression suite

Run from `frontend/` after installing the project dependencies and Chromium:

```sh
node node_modules/@playwright/test/cli.js install chromium
npm run test:e2e
```

The command type-checks the browser tests, builds the production frontend with its API URL fixed to `http://127.0.0.1:8018`, and starts dedicated local Uvicorn and Vite preview processes on ports 8018 and 4178. Node and uv must be available. Ports must be free: the suite refuses to borrow an existing server. No Azure, PostgreSQL or Foundry credentials are needed, and no analysis request is fabricated. The app's in-memory synthetic session API is real.

Four scenarios run in desktop Chromium (1280 × 800) and mobile Chromium (390 × 844):

- Home → create demo → play/pause → inclusive 62:00 goal → keyboard rewind to 61:59 → inspect metric and historical evidence → Fan/Analyst → Spanish. Assertions cover server score, hidden future context and retained cutoff.
- Browser offline/online recovery with the last confirmed cut, disabled controls and unchanged visible action list.
- Delete the owned session through the API, verify terminal UI and create another demo.
- Loaded image assets, no horizontal overflow, mobile menu, specialist selection, local rehearsal and return home.

Each test gets a fresh browser context, checks unhandled page exceptions and deletes only the sessions it creates. Playwright stops the owned web servers when the run ends. There are no fixed sleeps or screenshot pixel baselines; assertions wait for the actual UI or API condition. Retries are disabled so a flaky first attempt cannot silently pass.

Failures retain screenshots, video, event traces and an HTML report in ignored `test-results/` and `playwright-report/` directories. Successful climax screenshots are attached to the report. Inspect results with:

```sh
node node_modules/@playwright/test/cli.js show-report
```

To run one viewport: `npm run test:e2e -- --project=mobile`. CI runs the suite in its own `demo-e2e` job against a clean dependency install and uploads diagnostics for seven days. This validates the deterministic demo journey; real model inference remains a separate Foundry smoke test. Configuration follows the [Playwright test configuration](https://playwright.dev/docs/test-configuration) API.

The offline test exposed a paused stream that could remain open after networking failed. A failed/timed-out metric fetch now enters reconnection while retaining the confirmed view, rather than continuing to label the session connected; a unit regression covers this case too.
