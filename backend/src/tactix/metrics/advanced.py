"""Deterministic spatial metrics; all coordinates belong to the acting team."""

from collections import Counter, defaultdict, deque
from math import isfinite

from tactix.domain.common import Point
from tactix.domain.enums import EventType, Outcome
from tactix.domain.events import Event
from tactix.domain.metrics import (
    MetricsSnapshot,
    PassNetwork,
    PassNetworkEdge,
    PassNetworkNode,
    ShotMapEntry,
)
from tactix.metrics.core import CoreMetrics, _MetricValues, _time
from tactix.simulation.engine import MatchResult, PossessionFrame

METRICS_VERSION = "advanced-v1"
DEFENSIVE_WINS = (EventType.TACKLE, EventType.INTERCEPTION, EventType.DUEL)


def _betweenness(adjacency: dict[str, set[str]]) -> dict[str, float]:
    """Brandes for directed, unweighted paths, normalized by (n-1)(n-2)."""
    centrality = dict.fromkeys(adjacency, 0.0)
    for source in adjacency:
        predecessors = {node: [] for node in adjacency}
        paths = dict.fromkeys(adjacency, 0.0)
        paths[source] = 1.0
        distances = {source: 0}
        queue, stack = deque([source]), []
        while queue:
            node = queue.popleft()
            stack.append(node)
            for target in sorted(adjacency[node]):
                if target not in distances:
                    distances[target] = distances[node] + 1
                    queue.append(target)
                if distances[target] == distances[node] + 1:
                    paths[target] += paths[node]
                    predecessors[target].append(node)
        dependency = dict.fromkeys(adjacency, 0.0)
        for node in reversed(stack):
            for parent in predecessors[node]:
                dependency[parent] += paths[parent] / paths[node] * (1 + dependency[node])
            if node != source:
                centrality[node] += dependency[node]
    scale = (len(adjacency) - 1) * (len(adjacency) - 2)
    return {
        node: round(value / scale, 4) if scale > 0 else 0.0 for node, value in centrality.items()
    }


def _network(team: str, passes: list[Event]) -> PassNetwork:
    weights = Counter((e.player_id, e.related_player_id) for e in passes)
    locations = defaultdict(list)
    adjacency = {}
    incoming = defaultdict(set)
    for event in passes:
        actor, receiver = event.player_id, event.related_player_id
        adjacency.setdefault(actor, set()).add(receiver)
        adjacency.setdefault(receiver, set())
        incoming[receiver].add(actor)
        locations[actor].append(event.start)
        locations[receiver].append(event.end)
    between = _betweenness(adjacency)
    nodes = []
    for player in sorted(adjacency):
        points = locations[player]
        # Each completed pass contributes a send and receive observation, not tracking touches.
        nodes.append(
            PassNetworkNode(
                player_id=player,
                touches=len(points),
                degree_centrality=round(
                    (len(adjacency[player]) + len(incoming[player])) / (2 * (len(adjacency) - 1)), 4
                )
                if len(adjacency) > 1
                else 0.0,
                betweenness_centrality=between[player],
                avg_location=Point(
                    x=round(sum(p.x for p in points) / len(points), 4),
                    y=round(sum(p.y for p in points) / len(points), 4),
                ),
            )
        )
    return PassNetwork(
        team_id=team,
        nodes=nodes,
        edges=[
            PassNetworkEdge(from_player_id=actor, to_player_id=receiver, passes=count)
            for (actor, receiver), count in sorted(weights.items())
        ],
    )


class AdvancedMetrics(CoreMetrics):
    """Core-compatible accumulator with stricter spatial and shot-value input checks."""

    def push(self, frame: PossessionFrame) -> None:
        for event in frame.events:
            if event.type == EventType.SHOT and (
                event.expected_value is None
                or not isfinite(event.expected_value)
                or not 0 <= event.expected_value <= 1
            ):
                raise ValueError("Advanced metrics require a finite SHOT expected_value in [0,1]")
            if (
                event.type == EventType.PASS
                and event.outcome == Outcome.SUCCESS
                and event.end is None
            ):
                raise ValueError("Completed passes require an observed endpoint")
            if event.type in (*DEFENSIVE_WINS, EventType.FOUL):
                if event.team_id == frame.possession.team_id:
                    raise ValueError("Defensive actions must belong to the opposing team")
        super().push(frame)

    def snapshot(self, at_second: int | None = None) -> MetricsSnapshot:
        snapshot = super().snapshot(at_second)
        cutoff = (
            at_second
            if at_second is not None
            else (
                self._frames[-1].possession.end_minute * 60 + self._frames[-1].possession.end_second
                if self._frames
                else 0
            )
        )
        events = [e for f in self._frames for e in f.events if _time(e) <= cutoff]
        order = {e.id: i for i, e in enumerate(events)}
        completed = [e for e in events if e.type == EventType.PASS and e.outcome == Outcome.SUCCESS]
        final_third = [e for e in completed if e.start.x >= 200 / 3]
        for team in snapshot.teams:
            own = [e for e in events if e.team_id == team.team_id]
            shots = [e for e in own if e.type == EventType.SHOT]
            passes = [e for e in completed if e.team_id == team.team_id]
            builder = _MetricValues(order, cutoff)
            builder.add(
                "xg_like",
                "Synthetic expected goals",
                sum(e.expected_value for e in shots),
                shots,
                "Sum of SHOT expected_value from match-v1 synthetic heuristic; "
                "uncalibrated, not professional xG; GOAL markers excluded",
                "xG-like",
            )
            builder.count(
                "pass_network_passes",
                "Pass network observations",
                passes,
                "Completed PASS sources; send/start and receive/end observations. "
                "Directed edges carry pass counts; paths for betweenness are unweighted. "
                "Degree=(distinct incoming + outgoing neighbours)/(2*(n-1)). "
                "Betweenness normalized by (n-1)*(n-2), including disconnected nodes.",
            )
            team.pass_network = _network(team.team_id, passes)
            team.shot_map = [
                ShotMapEntry(
                    event_id=e.id,
                    player_id=e.player_id,
                    location=e.start.model_copy(deep=True),
                    xg=e.expected_value,
                    outcome=e.shot_outcome,
                )
                for e in shots
            ]
            rival_passes = [
                e
                for e in events
                if e.team_id != team.team_id and e.type == EventType.PASS and e.start.x <= 60
            ]
            actions = [
                e
                for e in own
                if e.start.x >= 40
                and (
                    e.type == EventType.FOUL
                    or e.type in DEFENSIVE_WINS
                    and e.outcome == Outcome.SUCCESS
                )
            ]
            builder.count(
                "ppda_opponent_passes",
                "PPDA opponent pass attempts",
                rival_passes,
                "Rival PASS attempts starting at rival x<=60 (own defensive 60%)",
            )
            builder.count(
                "ppda_defensive_actions",
                "PPDA defensive actions",
                actions,
                "Own x>=40: successful TACKLE/INTERCEPTION/DUEL or any FOUL; "
                "PRESS, RECOVERY, SAVE and BLOCK excluded",
            )
            if actions:
                builder.add(
                    "ppda",
                    "Passes per defensive action",
                    len(rival_passes) / len(actions),
                    rival_passes + actions,
                    f"Rival PASS attempts at rival x<=60 / own defensive actions at x>=40; "
                    f"{len(rival_passes)}/{len(actions)}; cutoff={cutoff}s",
                    "passes/action",
                )
            builder.ratio(
                "field_tilt",
                "Final-third completed-pass share",
                sum(e.team_id == team.team_id for e in final_third),
                len(final_third),
                final_third,
                "Team completed passes starting at own x>=200/3 / "
                "both teams' completed passes starting in their own attacking third",
            )
            team.values.extend(builder.values)
        return snapshot


def advanced_metrics_for_match(
    result: MatchResult, at_second: int | None = None
) -> MetricsSnapshot:
    engine = AdvancedMetrics(
        result.match_id,
        result.home_club_id,
        result.away_club_id,
        result.config.duration_minutes * 60,
    )
    engine.extend(result.frames)
    return engine.snapshot(at_second if at_second is not None else engine.duration_seconds)
