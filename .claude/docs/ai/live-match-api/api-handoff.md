# API Handoff: Live synthetic match sessions

## Business context

The frontend can select fictional clubs, create a deterministic match and follow
it against a shared controllable clock. Match observations and computed metrics
never reveal events after the visible clock. Multiple viewers follow the same
session without consuming one another's events. All endpoints are public demo
endpoints; there are no user roles or authentication in this delivery.

Base path: `/api/v1`. Interactive schema: `/docs`; machine schema: `/openapi.json`.
JSON property names use snake_case. Match events retain their existing domain shape.

## Endpoints

| Method and path | Request | Success | Errors |
|---|---|---|---|
| GET `/league` | None | 200: League, with clubs, squads and synthetic past fixtures | 500 if app startup failed |
| POST `/sessions` | Create request below | 201: SessionInfo; Location header points to session | 404 unknown club; 422 input; 503 capacity |
| GET `/sessions` | None | 200: SessionInfo[] | — |
| GET `/sessions/{id}` | Session UUID | 200: SessionInfo | 404 missing/expired |
| POST `/sessions/{id}/controls` | Discriminated control below | 200: ReplayUpdate without events | 404; 422 invalid control |
| DELETE `/sessions/{id}` | Session UUID | 204, empty body | 404 |
| GET `/sessions/{id}/events` | after_sequence=0, limit=100, optional revision | 200: EventPage | 404; 409 stale/future cursor; 422 query |
| GET `/sessions/{id}/metrics` | advanced=false, optional at_second | 200: MetricsResponse | 404; 409 revision changed; 422 future cut/query |
| GET `/sessions/{id}/stream` | Optional Last-Event-ID header | 200: text/event-stream | 400 invalid token; 404; 409 stale/future token; 422 header; 429 subscriber cap |

Create request, with every field optional:

```json
{
  "home": "Ashford",
  "away": "Northbridge",
  "match": {"engine_version": "match-v1", "seed": 42, "duration_minutes": 90},
  "speed": 60
}
```

Club selections accept an exact fictional name or ID from `/league`. The app's
league uses the default reproducible league-v3 configuration; changing match seed
changes the match, not the league. Each creation receives a new session UUID,
even when deterministic inputs produce the same match ID. Sessions start paused.

Control bodies are exactly one of:

```json
{"action":"play"}
{"action":"pause"}
{"action":"speed","speed":120}
{"action":"seek","second":2700}
```

## Data models / DTOs

```typescript
type Status = 'paused' | 'playing' | 'finished';
interface ReplayEvent { sequence: number; event: Event }
interface ReplayUpdate {
  replay_version: 'replay-v1';
  match_id: string;
  revision: number;
  position_seconds: number;
  duration_seconds: number;
  speed: number;
  status: Status;
  next_sequence: number;
  score: [number, number]; // home, away
  events: ReplayEvent[];
}
interface SessionInfo {
  session_id: string;
  scenario: 'procedural' | 'ashford-demo-v1';
  home_club_id: string;
  away_club_id: string;
  state: ReplayUpdate;
}
interface EventPage {
  revision: number;
  position_seconds: number;
  events: ReplayEvent[];
  next_sequence: number;
  has_more: boolean;
}
interface MetricsResponse {
  metrics_version: 'core-v1' | 'advanced-v1';
  at_second: number;
  revision: number;
  snapshot: MetricsSnapshot;
}
```

`Event`, `MetricsSnapshot` and `League` are described in OpenAPI. Metrics carry
`evidence.event_ids`; absent ratios mean no denominator, not zero. An advanced
snapshot adds xG-like totals, shot maps, directed pass networks, PPDA and field tilt.
The synthetic xG-like model is uncalibrated; labels must not imply professional xG.
Event coordinates use the acting team's own left-to-right attacking frame in both
halves. Mirror away events for a fixed-pitch display.

Sequence is the original one-based event index. `next_sequence` is cursor+1 in
event pages and SSE batches; pass `next_sequence - 1` as `after_sequence` to get
the next page. After N events the terminal value is N+1. State/control responses
are non-consuming clock observations: their event list is empty and their player
delivery cursor stays at 1. Use event pages or SSE cursors for delivery progress.

## Validation rules

- Extra JSON properties are rejected. Numeric strings and booleans are not accepted
  in place of strict numeric creation/control values.
- Home and away must differ. Names/IDs are nonempty, at most 100 characters.
- Match duration is an integer 2–90 minutes; seed is an integer 0 through 2^63-1.
  Only `match-v1` is accepted.
- Speed is finite, greater than zero and at most 10000. Default 60 gives one
  football minute per real second.
- Seek accepts finite fractional seconds from zero through match duration.
- Event page limit is 1–500; after_sequence and revision are nonnegative integers.
- Metrics cut is a nonnegative integer no later than floor(current clock).
  Omit it to use that floor automatically. Historical cuts remain available.

Validation errors use FastAPI's `{"detail":[...]}` shape. Application errors use
`{"detail":"message"}`. Capacity 503 carries Retry-After:30; subscriber 429 carries
Retry-After:5. JSON errors are returned before SSE headers for invalid resume tokens.

## SSE contract and reconnect

SSE frames have `event`, `id` and JSON `data`:

```text
event: replay
id: SESSION_UUID:0:1
data: {"replay_version":"replay-v1","match_id":"MATCH_ID","revision":0,"position_seconds":0.0,"duration_seconds":5400,"speed":60.0,"status":"paused","next_sequence":2,"score":[0,0],"events":[...]}
```

| Event name | Data | Client action |
|---|---|---|
| `replay` | ReplayUpdate | Apply clock/score and events in sequence order |
| `reset` | ReplayUpdate at new revision | Clear previous revision's panels; reconstruct visible history |
| `closed` | `{"session_id":"UUID"}` | Close EventSource and release the session view |

Playing sessions emit updates approximately every 100 ms, with all newly due events
batched. Scheduling and network delivery can vary. Paused sessions send their
initial state and wait for controls; SSE comment pings keep the connection alive
every 15 seconds. Sends have a 10-second timeout. Clients with slow consumption
catch up from retained events instead of dropping them or building tick queues.

The token `session_id:revision:last_sequence` acknowledges the highest delivered
sequence. On reconnect send it in Last-Event-ID: the response includes only later
events in that same revision. Browser EventSource handles this header on its own
automatic reconnects. An empty tick may reuse an ID; it does not advance the event
cursor. New connections without a token catch up from the current seek origin.

A token from a different session is 400. An old revision, a pre-seek cursor or a
cursor beyond the visible clock is 409. Fetch state, clear the prior revision's
view and create a **new** EventSource without the stale token. Do not retry an old
token forever. IDs identify delivery within this in-memory session, not a durable
message acknowledgement service. Deduplicate by session_id + revision + sequence.

Seek always pauses, increments revision and resets live delivery to the first
event at or after its target second. Active connections receive `reset`. Earlier
events are not replayed by the live seek batch. Rebuild history through `/events`
with the new revision, paging from zero, and merge by sequence to handle overlap
with concurrent SSE delivery. A 409 during reconstruction means restart at the
newest revision. The scoreboard is already reconstructed at the seek target.

## Integration notes

Recommended flow: fetch league, select clubs, create session, connect SSE, then
play. Render server clock/score rather than inventing a separate match clock.
Apply controls after their HTTP response; optimistic clock changes can race seek
revisions. Fetch metrics at a bounded UI cadence (for example once per real second),
not on every event. Store each metrics response with its `revision` and `at_second`;
discard stale revisions. Retry a 409 using the latest state.

```typescript
const source = new EventSource(`/api/v1/sessions/${sessionId}/stream`);
source.addEventListener('replay', event => {
  const update = JSON.parse((event as MessageEvent).data) as ReplayUpdate;
  render(update);
  if (update.status === 'finished') source.close();
});
source.addEventListener('reset', event => {
  const update = JSON.parse((event as MessageEvent).data) as ReplayUpdate;
  rebuildVisibleHistory(update.revision);
  render(update);
  if (update.status === 'finished') source.close();
});
source.addEventListener('closed', () => source.close());
```

Close on `finished` to prevent EventSource automatically reconnecting after normal
completion. The last event can precede the match end; wait for status, not an empty
batch. Half-time does not automatically pause. Disconnecting a viewer leaves the
shared clock and other viewers running. Deleting a session closes all its streams.
Metrics and event pages include only events at or before the captured clock.

Responses represent mutable live state; do not reuse them across revisions. SSE
uses Cache-Control:no-cache and X-Accel-Buffering:no. Existing development CORS
allows all origins. The frontend must close connections when unmounting or switching
sessions. Release unused sessions with DELETE to free capacity.

## Operating limits

### Authored Ashford demo

Add `"scenario":"ashford-demo-v1"` to the create body to select the authored
scenario. Keep Ashford home/Northbridge away, match seed 42 and duration 90; other
configurations are 422. Default scenario remains `procedural`.

For every session, GET `/sessions/{id}/league` resolves its own historical ledger.
The global `/league` still returns the procedural ledger, so fixture IDs differ
for demo sessions. GET `/sessions/{id}/context` on a demo session returns
`scenario_version`, `revision`, `at_second`, `historical_patterns`, nullable
`climax`, `verified_consecutive_matches`, `scorer_season_goals`,
`scorer_fixture_ids`, `scorer_live_goal_ids`, `earlier_meeting_fixture_ids` and
nullable `preview`. Procedural sessions return 409. This is an authored deterministic
preview, not agent output.

Before 62:00 `climax`/`preview` are null. At 62:00 the preview cites Hartley's actual
recorded count (ten), the twenty-second turnover sequence, and four consecutive
verified appearances. Pattern evidence identifies match, possession and event IDs.
GET `/sessions/{id}/history/{fixture_id}` resolves any of the four full historical
match artifacts; other fixtures and the live match ID return 404. Remaining
historical fixtures have summaries only. Use the usual seek/reset flow and discard
context from stale revisions. Seek to 3660, then play at 60x for a one-second lead-in.

### Session lifetime

The demo retains up to 16 sessions and permits 8 subscribers per session. Concurrent
match creation reservations also consume the session limit. Sessions disappear on
process restart; deploy this delivery with **one worker**. There is no distributed
session store, durable event delivery, user authorization or automatic expiry yet.
No database migration, agent orchestration or Azure deployment is part of this task.
Synthetic league history is available immediately; live match future events are not.

## Test scenarios

1. Two viewers subscribe, play and finish with identical event sequences.
2. Disconnect one viewer; reconnect its token and receive exactly the missing suffix.
3. Seek while connected: receive reset, clear old revision, rebuild historical panels.
4. Reconnect with an old revision: handle 409 by creating a fresh EventSource.
5. Request metrics beyond the clock: display 422 input error without leaking results.
6. Delete a session: active viewers receive closed; subsequent requests receive 404.
7. Hit session/subscriber caps: honor Retry-After and release unused resources.
8. Receive a final empty batch: close only when status is finished.
