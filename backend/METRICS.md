# Core metrics with source evidence

Compute an auditable snapshot from the full simulation JSON, from `backend/`:

```sh
uv run python -m tactix.metrics --input ../data/generated/match-42.json --output ../data/generated/metrics-42.json
uv run python -m tactix.metrics --input ../data/generated/match-42.json --at-second 2700
```

Generate that match with the commands in `SIMULATION.md` first. Input is the full
MatchResult JSON, including possession windows, not the event-only JSONL file.
Event-only data cannot reconstruct exact possession durations or dead time.
Output files must be new. The JSON output wraps the frozen MetricsSnapshot in
`metrics_version: core-v1`, the exact inclusive `at_second`, and `snapshot`.
No new database table, external service or language model is required.

## Python and incremental consumption

```python
from tactix.metrics.core import CoreMetrics, metrics_for_match

snapshot = metrics_for_match(result)  # At the configured match duration.
first_half = metrics_for_match(result, at_second=2700)

metrics = CoreMetrics(result.match_id, result.home_club_id, result.away_club_id,
                      result.config.duration_minutes * 60)
for frame in possession_stream:
    metrics.push(frame)
    live_snapshot = metrics.snapshot()
```

The accumulator consumes complete possession frames and snapshots their inputs.
It retains those frames so any past time cut can be recomputed exactly. It does
not mutate supplied frames or previously returned snapshots. Pushing a repeated
possession/event ID fails instead of counting it twice. Each push is atomic;
`extend` commits each accepted frame separately before attempting the next one.

The default accumulator snapshot uses the last supplied possession end, or zero
when empty. An explicit cut is an integer within the configured duration; it
describes the requested time, not a guarantee that a caller supplied a complete
stream through that time. Only observed supplied data contributes. Callers own
clock/completeness tracking. The batch helper receives a full result and defaults
to its configured final second, including the final dead-time interval.

## Metric definitions

Metrics are ordered consistently per home/away team. Counts use unit `count`,
time uses `s` and percentages use `%`. Values are rounded to four decimals.

| Key | Definition |
|---|---|
| possession_seconds | Sum of the team's recorded possession windows, clipped to the cut |
| possession_pct | Team seconds / both teams' observed possession seconds × 100 |
| possessions | Possession windows started by the cut, including an instant at kickoff |
| passes_attempted | PASS events only |
| passes_completed | Successful PASS events |
| pass_accuracy_pct | Completed / attempted passes × 100 |
| pass_share_pct | Team pass attempts / both teams' attempts × 100 |
| progressive_passes | Successful passes flagged progressive by the source |
| shots | SHOT events only, excluding GOAL and defensive BLOCK markers |
| shots_on_target | SHOT outcome GOAL, SAVED or ON_TARGET |
| shots_blocked | SHOT outcome BLOCKED |
| shots_off_target | SHOT outcome OFF_TARGET or POST |
| goals | GOAL markers with one matching scoring shot |
| saves | SAVE events credited to their acting team |
| shot_accuracy_pct | Shots on target / shots × 100 |
| pressures | PRESS and COUNTER_PRESS attempts |
| pressure_successes | SUCCESS pressure events backed by an attributed failed opponent action |
| pressure_success_pct | Successful pressures / attempts × 100 |
| recoveries | RECOVERY events only |
| high_recoveries | Recoveries with x ≥ 200/3 in the acting team's coordinate frame |
| turnovers | Completed possession windows ending in an explicit failed ball action and turnover outcome |

Time possession excludes gaps between possession windows. Pass share is a
separate measure and must not be labelled time possession. An on-target shot
saved by the goalkeeper counts for the shooter, while the save counts for the
opposing team. The source's short-lived pressure/goal markers do not create
additional time ownership or extra shots.

Ratios with zero denominators are omitted. For example, no shots means no
shot_accuracy_pct, whereas three missed shots means a measured accuracy of zero.
Empty input returns two teams with zero observed counts and no percentage keys;
it does not invent equal possession or a 0% accuracy measurement.

## Time cuts and evidence

Events at the cut's exact second are included. Future events are excluded, and
an ongoing possession's end is clipped to the cut. A future possession outcome
does not contribute to turnover counts before its recorded end. The frozen
snapshot has minute precision, so the CLI wrapper preserves the exact second.

Every value has an Evidence description and chronological, deduplicated event
IDs. Counts reference their counted events. Rates include denominator evidence:
pass accuracy includes failed attempts, pass share includes both teams' attempts,
and possession percentage includes observed events from both teams' windows.
Possession time additionally depends on the linked Possession start/end metadata;
the description names this rule instead of pretending event count measures time.

A successful pressure must match a failed opposing PASS, CARRY or DRIBBLE at the
same second in the same possession. The failed action must be under pressure and
name that exact presser, while the pressure names the failed actor. Evidence
includes both events; an unsupported SUCCESS flag is rejected rather than used
to invent a causal claim. This is attribution within synthetic source metadata,
not proof of a causal effect in real football.

## Validation and scope

Frames must be complete, chronological and non-overlapping, with a source event
at their start. IDs and references must agree with the match and possession.
Observed player/team associations must remain consistent; pass receivers must
be distinct teammates and defending pressure/save/block actions belong to the
opponent. Roster membership validation remains the simulation producer's job.
Goal markers and scoring shots must agree, with exactly one marker per scoring
shot. Shots require a classification. Rejected frames do not alter prior state.

Snapshots preserve MetricsSnapshot and TeamMetrics contracts. Pass networks,
shot maps/xG-like aggregates, PPDA, field tilt, ratings and momentum remain for
the existing advanced-metrics task; their optional fields retain their defaults.
The retained-source design is intended for one bounded match, not an unbounded
telemetry service. A snapshot scans observed events; successful-pressure support
also scans its own possession frame. No benchmark or concurrent-load claim is made.

Tests use independently calculated possession windows and scoreboards, explicit
denominator evidence, partial cuts, empty observations, defensive attribution,
goal deduplication, invalid inputs and real simulated matches. Run
`uv run pytest tests/unit/test_core_metrics.py -q`. Configure the existing
PostgreSQL test URL when running the entire backend suite.
