# Advanced deterministic metrics

`tactix.metrics.advanced` extends the core accumulator with version `advanced-v1`.
It preserves the frozen domain contracts and all core values. The default CLI and
`metrics_for_match` continue to produce `core-v1`; advanced computation is explicit.
No additional dependency, database migration or language model is required.

## Python and CLI

```python
from tactix.metrics.advanced import AdvancedMetrics, advanced_metrics_for_match

snapshot = advanced_metrics_for_match(result, at_second=2700)
live = AdvancedMetrics(result.match_id, result.home_club_id, result.away_club_id,
                       result.config.duration_minutes * 60)
for frame in result.frames:
    live.push(frame)
snapshot = live.snapshot(2700)
```

From `backend/`, using a full simulation JSON artifact:

```powershell
uv run python -m tactix.metrics --input ../data/generated/match-42.json --advanced --at-second 2700 --output ../data/generated/advanced-half.json
```

The output envelope records `metrics_version`, exact `at_second` and the frozen
`MetricsSnapshot`. Existing files are never overwritten. JSONL is not accepted.

## Exact definitions

All positions use the **acting team's** attack from x=0 towards x=100 in both
halves. Do not mirror the away team a second time.

| Key | Calculation | Evidence |
|---|---|---|
| `xg_like` | Sum SHOT `expected_value`, rounded to 4 decimals | SHOT IDs only |
| `pass_network_passes` | Number of successful PASS events represented in graph | Every completed PASS ID |
| `ppda_opponent_passes` | Rival PASS attempts starting at rival x<=60, including failed attempts | Qualifying rival PASS IDs |
| `ppda_defensive_actions` | Own successful TACKLE, INTERCEPTION or DUEL, or any FOUL, at own x>=40 | Qualifying own action IDs |
| `ppda` | `ppda_opponent_passes / ppda_defensive_actions` | Both numerator and denominator |
| `field_tilt` | 100 * own completed PASS starts at x>=200/3 / both teams' completed PASS starts in their respective attacking third | Both teams' qualifying PASS IDs |

The rival defensive 60% corresponds to the pressing team's attacking 60%:
own x = 100 - rival x. Thresholds are inclusive. Pass **starts**, rather than ends
or line crossings, determine territorial membership. The PPDA action convention
is specific to this version: failed tackles/duels and all PRESS, COUNTER_PRESS,
RECOVERY, SAVE and BLOCK events are excluded. It must not be compared as though
identical to an external data provider's metric.

Zero denominators omit the ratio; its component counts remain available. A genuine
zero numerator with a nonzero denominator yields zero. Field tilt measures a share
of observed passing activity, not possession time or spatial tracking dominance.

## Shot map and synthetic expected goals

Each `TeamMetrics.shot_map` entry links directly to its source SHOT event and
contains player, own-coordinate location, supplied expected value and outcome.
The simulator's `match-v1` supplies an uncalibrated geometric heuristic. This module
sums those supplied values; it does not refit or invent missing probabilities.
Every SHOT must have a finite value in [0,1] and a classified outcome. A GOAL marker
adds neither another shot nor more expected goals. Core validation still requires
exactly one source shot per goal marker.

## Directed pass network

Only successful PASS events enter the graph. Edges are directed sender to receiver;
`passes` counts repeated deliveries. Nodes include only observed senders and
receivers, not an inferred starting eleven or unused substitutes. A completed pass
requires an observed end location. IDs are sorted for deterministic serialization.

- `touches`: count of observed sends plus receptions from completed passes. This
  field is a pass involvement count, not all football touches.
- `avg_location`: mean of the node's observed send/start and receive/end positions.
  It is not a continuous tracking position or a formation estimate.
- `degree_centrality`: (distinct incoming neighbours + distinct outgoing neighbours)
  / (2 * (n-1)), bounded [0,1]. Reciprocal links count once in each direction.
- `betweenness_centrality`: directed, **unweighted** shortest-path betweenness,
  normalized by (n-1)*(n-2), including disconnected observed nodes. Equal shortest
  paths split credit. Fewer than three nodes gives zero. Pass frequency is carried
  by edge weights, not interpreted as a path distance. Brandes traversal is O(VE).

The `pass_network_passes` metric supplies the source event IDs for all network
fields without changing the existing `PassNetwork` contract.

## Time, validation and limitations

Cuts are inclusive and operate only on frames already supplied to the accumulator.
A frame is copied after all validation succeeds; rejection leaves state unchanged.
Returned snapshots and source inputs cannot mutate retained data. No future event,
receiver, shot or defensive action enters a historical cut. A new possession may
start at the previous possession's end second; a batch containing both frames has
more information at that second than a stream that has received only the first.
Compare batch and incremental results over the same received frames.

The core still retains complete frames to support historical cuts. This module is
not a bounded-memory streaming service. The simulator currently emits fouls rather
than a rich tackle/interception/duel stream, so its PPDA denominator can be sparse
or zero. Exposing both component counts makes that limitation inspectable. Do not
interpret a missing PPDA as an absence of pressure. Ratings, momentum, xT and
calibrated professional expected goals remain outside this task.

## Verification

`tests/unit/test_advanced_metrics.py` checks known graph centralities, equal-path
credit, disconnected nodes, reciprocal links, spatial thresholds, weighted edges,
source and snapshot isolation, missing denominators, shot/goal deduplication,
invalid input atomicity, inclusive cuts, incremental/batch equivalence and CLI
output protection. Generated-match tests verify that core values are unchanged.
