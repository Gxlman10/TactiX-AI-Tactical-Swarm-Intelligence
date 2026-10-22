# TactiX match studio

A local, interactive rehearsal of the Ashford–Northbridge demo. Built with React, strict TypeScript, Vite, Zustand and react-i18next. All clubs, players and events are fictional.

## Run

Use Node.js 24 (CI uses the same major version) and npm:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. No backend, database or Azure credentials are required for this rehearsal.

```sh
npm run lint
npm test
npm run build
npm run preview
```

The production output is in `dist/`. CI runs a clean install, lint, tests and the production build for every push to `dev` and every pull request.

## Explore

- Switch between English and Spanish or Analyst and Fan. Language and mode persist in local storage; the selected event stays intact when switching. Fan hides the metric strip; a complete fan narrative is a later integration.
- Play or pause the 61:00–63:00 clip at 1×, 4× or 12×. The slider also supports arrow keys. Playback stops at the end; Play then restarts the clip.
- Select a visible timeline action with a click, Tab/Enter or Space. Inspect its actor, coordinates, outcome, event ID and possession ID.
- The pitch shows recorded actions from the selected possession, not continuous player tracking. Coordinates are normalized to 0–100; away actions are mirrored on both axes to maintain a fixed home orientation.
- Rewind before 62:00: the goal, its score increment and the historical preview disappear. Future events stay hidden. At 62:00 the score is 1–1; the full source match eventually ends 2–2 outside this clip.

The context panel is explicitly labelled as a scripted preview. Neither a live SSE connection nor agent/model inference is active. Synthetic xG is an uncalibrated deterministic proxy, not a trained probability model.

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

The shell includes loading, error, empty and unknown-route states, keyboard controls, visible focus and reduced-motion handling. The `/api` development proxy is reserved for the later live integration; this version makes no API requests.
