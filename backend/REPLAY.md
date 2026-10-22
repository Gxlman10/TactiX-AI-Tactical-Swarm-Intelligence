# Match replay clock

`tactix.simulation.replay` plays an existing `MatchResult` against a monotonic clock.
The simulator still generates the same deterministic events without sleeping.
Playback is versioned separately as `replay-v1`; it does not change match identity.

## Run the CLI

From `backend/`, with an existing full simulation JSON artifact:

```powershell
uv run python -m tactix.simulation.replay --input ../data/generated/match-42.json --speed 60 --tick-seconds 0.1
uv run python -m tactix.simulation.replay --input ../data/generated/match-42.json --speed 120 --start-second 2700
```

The CLI flushes one `ReplayUpdate` JSON object per line to stdout, including clock
ticks with empty event batches. A speed of 60 means one football minute per real
second. The process exits after the configured match duration, not after its last
event. Ctrl+C cancels playback. Input is full JSON, not event-only JSONL. Files are
read only; there is no implicit regeneration or match mutation.

## Python controls

```python
from tactix.simulation.replay import MatchReplay

player = MatchReplay(result, speed=60)
player.play()
async for update in player.stream():
    await consume(update)
```

An application can call `pause()`, `play()`, `set_speed(120)` or `seek(2700)` on the
same event loop while consuming. These methods wake pending waits immediately.
Explicitly close an iterator with `await stream.aclose()` when abandoning it;
cancellation or closure pauses the player and releases the delivery cursor.

For synchronous adapters or controlled-clock tests, call `poll()` to deliver due
events. `snapshot()` observes clock, scoreboard and cursor without consuming any
event. An active asynchronous iterator owns delivery and blocks competing `poll()`
or stream consumers. This is one in-process timeline, not a broadcast service.

## State and timing

- Starts `paused` at second zero; its kickoff is due on the first poll. Repeated
  polls do not redeliver it. Speed must be finite and strictly positive.
- `play()` resumes from the current position. Repeated calls preserve continuity.
- `pause()` freezes football time; elapsed wall time during a pause does not count.
- `set_speed()` accounts for elapsed time at the old speed before adopting the new
  speed. It does not reset position, revision or event cursor.
- `seek(t)` accepts a finite number in [0, duration], **always pauses**, increments
  `revision` and places the cursor at the first original event with timestamp >= t.
  Events exactly at t are due on the next poll. Earlier events are deliberately
  skipped. Backward seeks allow explicit replay. Call `play()` to continue.
- Reaching duration changes state to `finished`. Further `play()` calls do not
  restart it. Seek backwards to start another traversal. Seeking to duration also
  finishes; any source event exactly at that second remains due.

The production clock is `time.monotonic`, so wall-clock corrections do not move a
match backwards. A `now` callback may be injected for tests; it must return finite,
nondecreasing seconds. Tick scheduling uses asyncio's event-loop clock. Football
time continues during consumer processing, and backpressure produces a catch-up
batch of all overdue events, without dropping them or accumulating queued ticks.
Paused streams wait for controls instead of emitting repeated idle ticks.

## Output contract and traceability

Each `ReplayUpdate` includes version, match ID, revision, fractional position in
seconds, configured duration, speed, status, next sequence, score and event batch.
Each delivery wraps an unchanged domain `Event` with its stable **one-based**
`sequence` in the original match event list. Equal timestamps retain original
list order (for example SHOT before GOAL). Eligibility is inclusive: timestamp <=
position. `next_sequence` is cursor+1; after all N events it is N+1.

Within one traversal each event is emitted once, locally. Consumers can identify
deliveries by `(match_id, revision, sequence)` and reset their accumulated view on
revision changes. There is no durable acknowledgement or exactly-once network
guarantee. A seek deliberately changes the traversal and can redeliver events.

The scoreboard counts GOAL markers at or before the clock position, independent of
whether the cursor already delivered them. Seeking reconstructs the visible score
without future goals. SHOT outcomes never double count the score. Snapshot packets
contain no event history; rebuild historical panels from the original artifact at
the requested cut, rather than treating a seek batch as the whole earlier match.

Input validation reuses core metrics checks for complete ordered possession frames,
event identity and references, timestamps, teams, pass receivers, pressure
attribution and goal-source consistency. Empty matches are rejected. This is
artifact validation, not a lineup or geometry audit: those require source clubs
and the simulator's `validate_match`. Source events and returned events are copied
so consumer mutations cannot change later traversals.

## Integration boundary

This task supplies a backend clock and adapter-ready stream. It does not add REST,
SSE, durable sessions, multiple subscribers, graphical controls or interpolation.
Original own-team coordinates remain unchanged. Consumers must apply display
mirroring separately. A half-time kickoff is an ordinary timestamped event;
playback does not automatically pause at half-time or invent whistle events.

For metrics on the full artifact, use the existing metrics API with
`at_second=int(update.position_seconds)`. That includes only events due by the
clock. Do not push partially received possessions to `CoreMetrics`: its incremental
API accepts complete frames, whose arrival can lag individual event delivery.

## Verification

`uv run pytest tests/unit/test_replay.py -q` tests clock continuity without real
match-length waits, stable simultaneous events, scoreboard cuts, seek semantics,
completion, immutable sources, invalid input, single-consumer ownership, control
wakeups, cancellation, backpressure, CLI JSONL and generated-match equivalence.
