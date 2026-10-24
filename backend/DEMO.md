# Ashford authored demo

`ashford-demo-v1` is an explicitly authored, wholly synthetic scenario. It supplies
the event-backed historical hook for the future Analyst → Historian → Narrator
handoff. It does not pretend that a seeded random simulation naturally produced
the planted story, and it does not implement the agents themselves.

## Committed recording fallback

A complete verified recording is committed in [data/recordings/ashford-demo-v1](../data/recordings/ashford-demo-v1/README.md). It contains all 649 live events, four historical artifacts and nine temporal checkpoints. `python -m tactix.demo.recording` can verify integrity and event-derived semantics, compare against regeneration, emit repeatable clip updates or extract the match for paced playback. This is a deterministic synthetic fallback; no agent inference or video is recorded. See its guide for tested commands and exact cutoff expectations.

## Reproduce and play

From `backend/`, export into a new directory:

```powershell
uv run python -m tactix.demo --config ../data/scenarios/ashford-demo.json --output-dir ../data/generated/ashford-demo-export
uv run python -m tactix.simulation.replay --input ../data/generated/ashford-demo-export/match.json --speed 60 --start-second 3660
```

The manifest pins league-v3 seed 42, match-v1 seed 42, twelve historical matchdays,
90-minute matches and the climax at second 3720. These are fixed requirements of
this scenario version; incompatible values are rejected. The output directory must
not exist. Generated files remain ignored by Git:

| File | Content |
|---|---|
| `bundle.json` | Version, scenario league, four event-backed historical matches, live match and authored goal ID |
| `league.json` | All sixty fixtures, recalculated table/form and head-to-head |
| `match.json` | Full live MatchResult, compatible with replay and metrics tools |
| `context-62.json` | Computed evidence and deterministic narrative preview at 62:00 |

For the HTTP demo, start the existing API and POST:

```json
{"scenario":"ashford-demo-v1","speed":60}
```

to `/api/v1/sessions`. Keep default Ashford home/Northbridge away and the default
match seed/duration. Open its normal SSE endpoint. Seek to second 3660, then play
to reach the climax in one real second at 60x. The existing controls, metrics,
revisions and resume tokens work unchanged. Procedural sessions remain the default.

## What is authored

The scenario starts with the full procedural league and matches. It overlays a
short sequence in Ashford's last three historical fixtures (matchdays 10–12), an
earlier meeting with Northbridge (matchday 6), and the live Ashford–Northbridge
fixture. The surrounding match retains hundreds of procedural events.

1. An Ashford possession receives support into midfield.
2. At 61:40 a pressured pass starts at x=50 and fails.
3. At 61:48 the rival recovers at the mirrored location of the failed pass's end.
4. A completed pass reaches the scorer in the attacking left channel (x=82,y=25).
5. At 62:00 a scoring SHOT creates exactly one linked GOAL. Finn Hartley is the live
   scorer and the scorer in the earlier Northbridge meeting.
6. Ashford kicks off at 62:08 and reconnects to the remaining procedural sequence.

This is a repeatable authored mechanism, not an emergent probability claim. The
historical clips intentionally share its timing. The overlay replaces the source
segment through the next suitable Ashford possession, so scores and possession
totals may differ from the procedural match. Every resulting match passes the
existing lineup, timing, geometry, goal linkage, phase and restart validators, plus
advanced metrics input validation. Source club/player snapshots are unchanged.

League, fixture, match, possession and event identities are namespaced by scenario
version; player and club identities retain the source roster. The underlying match
configuration records the base `match-v1` engine. Interpret the authored match
together with its outer scenario version, rather than reproducing it from the base
match config alone. Changing this published scenario requires a new version.

## Derived history and evidence

The four historical match artifacts determine their fixture scores, scorer records,
xG-like totals and possession percentages. Standings, form and head-to-head are
then rebuilt from the full sixty-fixture ledger and validated. The remaining
fifty-six fixtures retain their original synthetic summaries; no event stream or
midfield-turnover evidence is invented for them.

`midfield_concessions` inspects adjacent possession chains. It requires a failed
PASS/CARRY/DRIBBLE starting at x in [40,60], an opposing RECOVERY at the mirrored
loss endpoint, and a linked scoring shot/goal within thirty seconds. The scorer,
team and timestamp must agree. Its `PatternEvidence` identifies both possessions
and the loss, recovery, shot and goal event IDs. Labels in `pattern_note` do not
create evidence. It expects a validated, complete MatchResult.

`demo_context(bundle, at_second)` inspects historical artifacts and the visible
live cut. Before 3720 its `climax` and `preview` are null. At 3720 the pattern is
visible with an elapsed twenty seconds and four verified consecutive appearances
(the last three historical appearances plus this live match). This is a verified
sample, not a claim that the pattern was absent in older unaudited fixtures.

Hartley's season count comes from all recorded fixture scorers plus his visible
live GOAL markers. The initial scenario has **ten** recorded goals at 62:00, not
the illustrative third goal in the README. `scorer_fixture_ids`,
`scorer_live_goal_ids` and `earlier_meeting_fixture_ids` make those facts inspectable.
The preview is a deterministic fixture for testing narrative provenance, not an
output from an agent or evidence of deployed orchestration. It claims a left-channel
location for this shot only; it does not infer locations for summary-only goals.

## Context endpoints

| Endpoint under `/api/v1/sessions/{id}` | Behavior |
|---|---|
| GET `/league` | Session-specific league, including the authored ledger when selected |
| GET `/context` | Scenario version, clock cut, revision, historical pattern evidence, nullable live climax, derived counts and preview |
| GET `/history/{fixture_id}` | Full event artifact for one of the four historical fixtures |

`/context` returns 409 on procedural sessions. Missing historical artifacts return
404, including requests using the live match ID. The global `/api/v1/league` remains
the default procedural league. For a demo session use its session-specific league
to resolve fixture IDs and reconcile counts. The context cut is controlled by the
session clock; callers cannot request future narrative evidence. All these
endpoints inherit the existing temporary, single-worker session limits.

## Verification

`uv run pytest tests/unit/test_demo.py -q` checks byte-reproducible bundles,
procedural baseline isolation, every authored match against full validators,
fixture/metrics reconciliation, complete historical backing, inclusive climax cuts,
actual scorer ledgers, malformed causal links, changed supporting evidence, manifest
validation, export overwrite protection, API opt-in constraints and SSE delivery.
