# Deterministic possession and event engine

From `backend/`, create a full synthetic match or an ordered event stream:

```sh
uv run python -m tactix.simulation --config ../data/scenarios/match-base.json --output ../data/generated/match-42.json
uv run python -m tactix.simulation --config ../data/scenarios/match-base.json --format jsonl --output ../data/generated/match-42.jsonl
uv run python -m tactix.simulation --duration-minutes 10 --seed 7
```

Outputs must be new files. The versioned manifest chooses league-v3 seed 42,
Ashford versus Northbridge and match-v1 seed 42. `--seed` changes the match seed
only, retaining the source league, players and historical context. Choose a club
by exact name or ID with `--home` and `--away`.

No database, model service or wall-clock sleeps are required. The existing
universe generator supplies the inputs. Its historical fixtures use their own
summary generator; they are not silently replaced with this live-event model.

## Public interface

```python
from tactix.simulation.engine import MatchConfig, iter_events, iter_possessions, simulate_match
from tactix.universe.generator import generate_league

league = generate_league()
home, away = league.clubs[:2]
config = MatchConfig(seed=42, duration_minutes=90)
result = simulate_match(home, away, config)
home_goals, away_goals = result.score

for frame in iter_possessions(home, away, config):
    possession = frame.possession
    phase_path = frame.phases
    ordered_events = frame.events

for event in iter_events(home, away, config):
    pass  # Feed deterministic Event objects to a consumer.
```

Iteration constructs a completed possession before yielding its events. It
does not wait for match time or provide pause/resume controls; playback with a
clock and SSE remain separate tasks. Calling either iterator starts an
independent deterministic run, rather than consuming an existing result.

The JSON artifact contains match/club IDs, configuration and frames. Each frame
contains one frozen-contract Possession, its Event objects and the internal
phase path. JSONL contains only ordered Event records, one per line. The result's
`events` and `score` are Python properties derived from frames, not redundant
stored fields. Reconstruct JSON with `MatchResult.model_validate_json` and use
`validate_match(result, home, away)` to verify it against the source lineups.

## Possession state machine

The phase path is build_up → progression → final_third → outcome. A turnover,
foul, clearance or period boundary may end a chain early. Ball x ≥ 40 advances
to progression and x ≥ 70 to final third; a long restart or pass may cross both
boundaries in one action. The trace records visited states, not a claim that
each state lasted a distinct time interval. The Possession contract keeps the
terminal outcome phase; detailed phase history stays in the frame wrapper.

Successful passes transfer the ball to a distinct teammate receiver; carries
and dribbles retain the actor. A failed action transfers ownership to the
opponent through an explicit recovery. A sequence is limited to twelve ball
actions; an explicit clearance ends longer sequences instead of a silent flip.
Defensive pressure, fouls, saves and blocks belong to the acting opponent but
remain linked to the attacking possession they affected.

| Outcome | Next restart | Possessing team |
|---|---|---|
| Goal | Kickoff | Conceding team |
| Turnover, clearance or retained block | Recovery | Opponent |
| Saved or off-target shot | Goal kick | Opponent |
| Block deflected for a corner | Corner | Attacking team |
| Foul won | Free kick | Attacking team |
| Period end | Scheduled kickoff or end of run | Next period's designated team |

Home kicks off the first period and away the second. Configurable durations
are integer 2–90 minutes, split evenly, including second-based boundaries for
odd durations. Event timestamps never decrease; related actions such as shot
and save share a timestamp and retain stable list order. Eight seconds between
possessions represent reset/stoppage time outside possession duration. A final
reset may reach the period boundary without a whistle event; the enum has no
whistle type. No possession crosses halftime or the configured end.

## Spatial conventions and traceability

Every event uses the acting team's attacking-left-to-right 100×100 frame,
including defensive events. Opponent actions are mirrored on both axes. A
viewer using a fixed physical pitch must mirror away events into its chosen
display frame. This convention is the same in both periods.

Distances scale normalized coordinates to a 105×68 metre pitch. Ordinary action
angles are signed direction radians; shot angles are the positive goal opening
between 7.32-metre posts. Zones are three longitudinal thirds by six lateral
channels, numbered 1–18. A ball movement is progressive when end.x − start.x ≥ 10;
this is an explicit synthetic threshold, not an official competition definition.

Each event links to its match and possession, which lists the exact event IDs
in order. Passes identify receivers; pressure identifies an opposing presser.
Shots carry body part, endpoint, geometry-based expected value and terminal
shot outcome. A scoring shot produces one separate GOAL event whose subtype
is `from_shot:<shot-id>`. Count GOAL events for the scoreboard; count SHOT events
for attempts and xG-like totals. Non-scoring shots have outcome FAIL, with their
more specific result in shot_outcome. On-target shots are GOAL or SAVED.

## Design rules and limitations

`rules.py` holds the original bounded execution and spatial rules. Direct
build-up selects longer passes; width changes lateral targets; tempo affects
action duration; opponent pressing intensity affects exposure to pressure.
Passing, long passing, decisions, composure, control, speed and dribbling affect
execution according to the action and distance.

Effective fatigue is initial fatigue plus minute/90 × (100 − stamina), capped
at 100. It reduces execution and shot conversion without mutating player state.
Shot conversion also uses finishing, goalkeeper reflexes and pressure. The
coordinate-based expected value is an original uncalibrated design rule, not
official xG or a learned prediction. Its value belongs only to the SHOT record.

The first eleven roster entries are the active lineup. Suspended starters,
missing goalkeeper attributes, incomplete lineups and duplicate player IDs
are rejected. There are no substitutions, cards, injuries, offsides, penalties,
stoppage-time additions, continuous player tracking or full physical simulation
in this delivery. Pass/shot distance is ball distance, not player running distance.
No historical Ashford pattern or planted climax is injected here.

Match identity incorporates the engine configuration and full source club
snapshots. Each possession has its own private random stream and deterministic
event IDs. Inputs are copied, global random state is untouched and yielded
events are never revised later. A behavior change requires a new engine version
before changing a published fixture's reproducibility contract.

## Checks

Run `uv run pytest tests/unit/test_simulation.py -q` for the focused checks.
They cover multiple seeds, full and short games, odd period boundaries,
ownership, references, pass continuity, goal deduplication, restarts, causal
fatigue/pressure/skill rules, tactical pass-length effects, input immutability,
invalid artifacts, CLI export and equivalence of eager/lazy event streams.
Use the existing PostgreSQL test configuration when running the entire backend
suite. This task adds no database migration or match-event persistence layer.
