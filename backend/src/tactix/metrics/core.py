"""Auditable core metrics from complete possession frames, with inclusive time cuts."""

from collections import Counter
from collections.abc import Iterable

from tactix.domain.enums import EventType, Outcome, PossessionPhase, ShotOutcome
from tactix.domain.events import Event
from tactix.domain.metrics import Evidence, MetricsSnapshot, MetricValue, TeamMetrics
from tactix.simulation.engine import MatchResult, PossessionFrame

METRICS_VERSION = "core-v1"
PRESSURES = (EventType.PRESS, EventType.COUNTER_PRESS)
BALL_ACTIONS = (EventType.PASS, EventType.CARRY, EventType.DRIBBLE)


def _time(event: Event) -> int:
    return event.minute * 60 + event.second


def _window(frame: PossessionFrame) -> tuple[int, int]:
    p = frame.possession
    return p.start_minute * 60 + p.start_second, p.end_minute * 60 + p.end_second


def _pressure_support(pressure: Event, events: list[Event]) -> list[Event]:
    return [
        event
        for event in events
        if event.type in BALL_ACTIONS
        and event.outcome == Outcome.FAIL
        and event.team_id != pressure.team_id
        and event.player_id == pressure.related_player_id
        and event.under_pressure
        and event.pressured_by == pressure.player_id
        and _time(event) == _time(pressure)
    ]


class _MetricValues:
    def __init__(self, event_order: dict[str, int], cutoff: int):
        self.event_order = event_order
        self.cutoff = cutoff
        self.values: list[MetricValue] = []

    def add(
        self,
        key: str,
        label: str,
        value: float,
        sources: list[Event],
        description: str,
        unit: str = "count",
    ) -> None:
        ids = sorted({e.id for e in sources}, key=self.event_order.__getitem__)
        self.values.append(
            MetricValue(
                key=key,
                label=label,
                value=round(value, 4),
                unit=unit,
                evidence=Evidence(event_ids=ids, description=description),
            )
        )

    def count(self, key: str, label: str, sources: list[Event], description: str) -> None:
        self.add(key, label, len(sources), sources, description)

    def ratio(
        self,
        key: str,
        label: str,
        numerator: float,
        denominator: float,
        sources: list[Event],
        description: str,
    ) -> None:
        if denominator:
            self.add(
                key,
                label,
                100 * numerator / denominator,
                sources,
                f"{description}; {numerator}/{denominator} x 100; cutoff={self.cutoff}s",
                "%",
            )


class CoreMetrics:
    """Retain immutable input snapshots; recompute exact, evidence-bearing cuts.

    Each push is atomic. Retaining source frames makes past cuts reproducible;
    computation is linear in observed events plus pressure attribution within frames.
    No database, language model or clock scheduling is involved.
    """

    def __init__(self, match_id: str, home_id: str, away_id: str, duration_seconds: int = 5400):
        if not match_id or not home_id or not away_id or home_id == away_id:
            raise ValueError("A match and two distinct nonempty team IDs are required")
        if type(duration_seconds) is not int or not 1 <= duration_seconds <= 5400:
            raise ValueError("duration_seconds must be an integer between 1 and 5400")
        self.match_id = match_id
        self.team_ids = (home_id, away_id)
        self.duration_seconds = duration_seconds
        self._frames: list[PossessionFrame] = []
        self._event_ids: set[str] = set()
        self._possession_ids: set[str] = set()
        self._player_teams: dict[str, str] = {}

    def push(self, frame: PossessionFrame) -> None:
        """Accept one complete frame; repeated deliveries are rejected, not recounted."""
        p = frame.possession
        began, ended = _window(frame)
        if p.match_id != self.match_id or p.team_id not in self.team_ids:
            raise ValueError("Possession references a different match or unknown team")
        if p.phase != PossessionPhase.OUTCOME:
            raise ValueError("Only complete possession frames may be pushed")
        if p.id in self._possession_ids or not p.id:
            raise ValueError("Duplicate or empty possession ID")
        if (
            not 0 <= began <= ended <= self.duration_seconds
            or (self._frames and began < _window(self._frames[-1])[1])
            or not (0 <= p.start_second < 60 and 0 <= p.end_second < 60)
        ):
            raise ValueError("Possession windows must be normalized, ordered and within the match")
        events = frame.events
        ids = [event.id for event in events]
        if (
            not events
            or p.event_ids != ids
            or len(set(ids)) != len(ids)
            or (self._event_ids.intersection(ids))
            or any(not key for key in ids)
        ):
            raise ValueError("Possession event links must be complete, nonempty and unique")
        times = [_time(e) for e in events]
        if times != sorted(times) or min(times) != began or max(times) > ended:
            raise ValueError("Event times must be ordered and inside the possession")
        shots = {e.id: e for e in events if e.type == EventType.SHOT}
        goals = Counter()
        players = dict(self._player_teams)

        def bind(player_id: str | None, team: str) -> None:
            if not player_id or (player_id in players and players[player_id] != team):
                raise ValueError("Player references must be nonempty and team-consistent")
            players[player_id] = team

        for event in events:
            bind(event.player_id, event.team_id)
        for event in events:
            if (
                event.match_id != self.match_id
                or event.possession_id != p.id
                or (event.team_id not in self.team_ids or not 0 <= event.second < 60)
            ):
                raise ValueError("Event references a different match, possession or team")
            defending = event.type in (*PRESSURES, EventType.SAVE, EventType.BLOCK)
            attacking = event.type in (
                *BALL_ACTIONS,
                EventType.SHOT,
                EventType.GOAL,
                EventType.RECOVERY,
                EventType.KICKOFF,
                EventType.GOAL_KICK,
                EventType.CORNER,
                EventType.FREE_KICK,
            )
            if (defending and event.team_id == p.team_id) or (
                attacking and event.team_id != p.team_id
            ):
                raise ValueError("Event team disagrees with its possession role")
            if event.under_pressure != (event.pressured_by is not None):
                raise ValueError("Pressure flag and reference disagree")
            opponent = self.team_ids[1] if event.team_id == self.team_ids[0] else self.team_ids[0]
            if event.pressured_by:
                bind(event.pressured_by, opponent)
            if defending and event.related_player_id:
                bind(event.related_player_id, opponent)
            if event.type == EventType.PASS and (
                not event.related_player_id or event.related_player_id == event.player_id
            ):
                raise ValueError("Passes require a distinct receiver")
            if event.type == EventType.PASS:
                bind(event.related_player_id, event.team_id)
            if event.type == EventType.SHOT and event.shot_outcome is None:
                raise ValueError("Shot classification is required")
            if event.type == EventType.GOAL:
                if not (event.subtype or "").startswith("from_shot:"):
                    raise ValueError("Goals require a source shot ID")
                shot_id = event.subtype.removeprefix("from_shot:")
                source = shots.get(shot_id)
                if (
                    source is None
                    or source.shot_outcome != ShotOutcome.GOAL
                    or (source.team_id, source.player_id, _time(source))
                    != (event.team_id, event.player_id, _time(event))
                ):
                    raise ValueError("Goal and source shot disagree")
                goals[shot_id] += 1
            if (
                event.type in PRESSURES
                and event.outcome == Outcome.SUCCESS
                and not (_pressure_support(event, events))
            ):
                raise ValueError("Successful pressure requires an attributed rival turnover")
        if any(
            goals[key] != int(shot.shot_outcome == ShotOutcome.GOAL) for key, shot in shots.items()
        ):
            raise ValueError("Each scoring shot must have exactly one goal marker")
        if p.outcome == "turnover" and (
            events[-1].type not in BALL_ACTIONS
            or events[-1].outcome != Outcome.FAIL
            or events[-1].team_id != p.team_id
        ):
            raise ValueError("Turnover classification requires a terminal failed ball action")
        # Only update internal state after all validation has passed.
        self._frames.append(frame.model_copy(deep=True))
        self._event_ids.update(ids)
        self._possession_ids.add(p.id)
        self._player_teams = players

    def extend(self, frames: Iterable[PossessionFrame]) -> None:
        """Push frames in order; atomicity applies to each frame, not the whole iterable."""
        for frame in frames:
            self.push(frame)

    def snapshot(self, at_second: int | None = None) -> MetricsSnapshot:
        cutoff = (
            at_second
            if at_second is not None
            else (_window(self._frames[-1])[1] if self._frames else 0)
        )
        if type(cutoff) is not int or not 0 <= cutoff <= self.duration_seconds:
            raise ValueError("Snapshot cutoff must be an integer inside the match duration")
        frames = [f for f in self._frames if _window(f)[0] <= cutoff]
        visible = {f.possession.id: [e for e in f.events if _time(e) <= cutoff] for f in frames}
        events = [e for f in frames for e in visible[f.possession.id]]
        event_order = {e.id: i for i, e in enumerate(events)}
        duration = {
            team: sum(
                max(0, min(_window(f)[1], cutoff) - _window(f)[0])
                for f in frames
                if f.possession.team_id == team
            )
            for team in self.team_ids
        }
        all_passes = [e for e in events if e.type == EventType.PASS]
        teams = []
        for team in self.team_ids:
            own = [e for e in events if e.team_id == team]
            passes = [e for e in own if e.type == EventType.PASS]
            completed = [e for e in passes if e.outcome == Outcome.SUCCESS]
            shots = [e for e in own if e.type == EventType.SHOT]
            targets = [
                e
                for e in shots
                if e.shot_outcome in (ShotOutcome.GOAL, ShotOutcome.SAVED, ShotOutcome.ON_TARGET)
            ]
            goals = [e for e in own if e.type == EventType.GOAL]
            pressures = [e for e in own if e.type in PRESSURES]
            wins = [e for e in pressures if e.outcome == Outcome.SUCCESS]
            pressure_evidence = [
                e
                for pressure in wins
                for e in (pressure, *_pressure_support(pressure, visible[pressure.possession_id]))
            ]
            own_frames = [f for f in frames if f.possession.team_id == team]
            owner_evidence = [e for f in own_frames for e in visible[f.possession.id]]
            turnovers = [
                f
                for f in own_frames
                if _window(f)[1] <= cutoff and f.possession.outcome == "turnover"
            ]
            builder = _MetricValues(event_order, cutoff)
            add, count, ratio = builder.add, builder.count, builder.ratio

            add(
                "possession_seconds",
                "Possession time",
                duration[team],
                owner_evidence,
                f"Sum of recorded Possession windows clipped at {cutoff}s; dead time excluded. "
                "Boundaries and ownership come from possessions linked by these events.",
                "s",
            )
            ratio(
                "possession_pct",
                "Possession",
                duration[team],
                sum(duration.values()),
                events,
                "Team possession seconds / total observed possession seconds; excludes dead time",
            )
            add(
                "possessions",
                "Possessions started",
                len(own_frames),
                owner_evidence,
                "Count possession windows started by the cutoff, including zero-time starts",
            )
            count("passes_attempted", "Passes attempted", passes, "Count PASS events only")
            count(
                "passes_completed",
                "Passes completed",
                completed,
                "PASS events with SUCCESS outcome",
            )
            ratio(
                "pass_accuracy_pct",
                "Pass accuracy",
                len(completed),
                len(passes),
                passes,
                "Completed passes / attempted passes",
            )
            ratio(
                "pass_share_pct",
                "Share of pass attempts",
                len(passes),
                len(all_passes),
                all_passes,
                "Team pass attempts / both teams' pass attempts; not time possession",
            )
            count(
                "progressive_passes",
                "Progressive passes completed",
                [e for e in completed if e.progressive],
                "Completed PASS events flagged progressive",
            )
            count(
                "shots",
                "Shots",
                shots,
                "Count SHOT events; never count GOAL markers as extra shots",
            )
            count(
                "shots_on_target",
                "Shots on target",
                targets,
                "SHOT outcomes GOAL, SAVED or ON_TARGET",
            )
            count(
                "shots_blocked",
                "Shots blocked",
                [e for e in shots if e.shot_outcome == ShotOutcome.BLOCKED],
                "SHOT events with BLOCKED outcome; not defensive BLOCK events",
            )
            count(
                "shots_off_target",
                "Shots off target",
                [e for e in shots if e.shot_outcome in (ShotOutcome.OFF_TARGET, ShotOutcome.POST)],
                "SHOT outcomes OFF_TARGET or POST",
            )
            count(
                "goals", "Goals", goals, "GOAL markers validated against exactly one scoring shot"
            )
            count(
                "saves",
                "Saves",
                [e for e in own if e.type == EventType.SAVE],
                "SAVE events credited to the acting team, not the attacking possession owner",
            )
            ratio(
                "shot_accuracy_pct",
                "Shot accuracy",
                len(targets),
                len(shots),
                shots,
                "Shots on target / shots",
            )
            count("pressures", "Pressure attempts", pressures, "PRESS and COUNTER_PRESS events")
            add(
                "pressure_successes",
                "Successful pressures",
                len(wins),
                pressure_evidence,
                "SUCCESS pressure events backed by an opposing failed ball action at the same time "
                "and possession with a matching pressured_by reference",
            )
            ratio(
                "pressure_success_pct",
                "Pressure success",
                len(wins),
                len(pressures),
                pressures + pressure_evidence,
                "Attributed pressure successes / pressure attempts",
            )
            count(
                "recoveries",
                "Recoveries",
                [e for e in own if e.type == EventType.RECOVERY],
                "RECOVERY events only; avoid counting a separate interception marker twice",
            )
            count(
                "high_recoveries",
                "High recoveries",
                [e for e in own if e.type == EventType.RECOVERY and e.start.x >= 200 / 3],
                "RECOVERY events in the acting team's attacking third (x >= 200/3)",
            )
            add(
                "turnovers",
                "Possessions lost",
                len(turnovers),
                [e for f in turnovers for e in visible[f.possession.id]],
                "Completed possession windows ending in turnover; future outcomes are excluded",
            )
            teams.append(TeamMetrics(team_id=team, values=builder.values))
        return MetricsSnapshot(match_id=self.match_id, minute=cutoff // 60, teams=teams)


def metrics_for_match(result: MatchResult, at_second: int | None = None) -> MetricsSnapshot:
    engine = CoreMetrics(
        result.match_id,
        result.home_club_id,
        result.away_club_id,
        result.config.duration_minutes * 60,
    )
    engine.extend(result.frames)
    return engine.snapshot(at_second if at_second is not None else engine.duration_seconds)
