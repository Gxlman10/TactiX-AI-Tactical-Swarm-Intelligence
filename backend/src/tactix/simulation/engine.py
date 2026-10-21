"""Seeded possession state machine. Iteration advances football time without sleeps."""

import hashlib
import random
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from tactix.domain.common import Point
from tactix.domain.enums import (
    BodyPart,
    BuildUpStyle,
    EventType,
    Foot,
    Outcome,
    PlayPattern,
    Position,
    PossessionPhase,
    ShotOutcome,
)
from tactix.domain.events import Event, Possession
from tactix.domain.universe import Club, Player
from tactix.simulation.rules import (
    action_probability,
    direction,
    distance,
    fatigue,
    mirror,
    pitch_zone,
    shot_angle,
    shot_value,
)


class MatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    engine_version: Literal["match-v1"] = "match-v1"
    seed: int = Field(default=42, ge=0, le=2**63 - 1)
    duration_minutes: int = Field(default=90, ge=2, le=90)


class PossessionFrame(BaseModel):
    possession: Possession
    phases: list[PossessionPhase]
    events: list[Event]


class MatchResult(BaseModel):
    match_id: str
    home_club_id: str
    away_club_id: str
    config: MatchConfig
    frames: list[PossessionFrame]

    @property
    def events(self) -> list[Event]:
        return [event for frame in self.frames for event in frame.events]

    @property
    def score(self) -> tuple[int, int]:
        return tuple(
            sum(event.type == EventType.GOAL and event.team_id == club_id for event in self.events)
            for club_id in (self.home_club_id, self.away_club_id)
        )


@dataclass
class _Restart:
    owner: int
    kind: EventType
    point: Point
    player_id: str | None = None


def _validate_clubs(home: Club, away: Club) -> None:
    if home.id == away.id:
        raise ValueError("A club cannot play itself")
    ids = [p.id for club in (home, away) for p in club.squad]
    if len(ids) != len(set(ids)):
        raise ValueError("Player IDs must be unique across both squads")
    for club in (home, away):
        starters = club.squad[:11]
        if len(starters) != 11 or any(not p.positions for p in starters):
            raise ValueError("Each club requires eleven positioned starting players")
        keepers = [p for p in starters if Position.GK in p.positions]
        if len(keepers) != 1 or keepers[0].goalkeeping is None:
            raise ValueError("Each starting lineup requires one goalkeeper with attributes")
        if any(p.state.suspended for p in starters):
            raise ValueError("Suspended players cannot start; select an eligible lineup first")


class _Match:
    def __init__(self, home: Club, away: Club, config: MatchConfig):
        _validate_clubs(home, away)
        # Snapshot inputs so caller mutations between yields cannot alter a run.
        self.clubs = [home.model_copy(deep=True), away.model_copy(deep=True)]
        self.config = config
        digest = hashlib.sha256(
            (home.model_dump_json() + away.model_dump_json() + config.model_dump_json()).encode()
        ).hexdigest()
        self.namespace = uuid5(NAMESPACE_URL, f"tactix:{config.engine_version}:{digest}")
        self.match_id = str(self.namespace)
        self.clock, self.number = 0, 0

    def _outfield(self, owner: int) -> list[Player]:
        return [p for p in self.clubs[owner].squad[:11] if Position.GK not in p.positions]

    def _keeper(self, owner: int) -> Player:
        return next(p for p in self.clubs[owner].squad[:11] if Position.GK in p.positions)

    def _possession(self, restart: _Restart, period_end: int) -> tuple[PossessionFrame, _Restart]:
        owner, opponent = restart.owner, 1 - restart.owner
        club, rival = self.clubs[owner], self.clubs[opponent]
        possession_id = uuid5(self.namespace, f"possession:{self.number}")
        rng = random.Random(int.from_bytes(hashlib.sha256(str(possession_id).encode()).digest()))
        self.number += 1
        events: list[Event] = []
        phases = [PossessionPhase.BUILD_UP]
        began = self.clock
        point = restart.point
        pattern = {
            EventType.KICKOFF: PlayPattern.OPEN_PLAY,
            EventType.CORNER: PlayPattern.FROM_CORNER,
            EventType.FREE_KICK: PlayPattern.FROM_FREE_KICK,
            EventType.GOAL_KICK: PlayPattern.GOAL_KICK,
            EventType.THROW_IN: PlayPattern.FROM_THROW_IN,
            EventType.RECOVERY: PlayPattern.COUNTER,
        }[restart.kind]
        if restart.player_id:
            carrier = next(p for p in club.squad[:11] if p.id == restart.player_id)
        elif restart.kind == EventType.GOAL_KICK:
            carrier = self._keeper(owner)
        else:
            carrier = rng.choice(self._outfield(owner))

        def emit(
            team: int,
            player: Player,
            kind: EventType,
            start: Point,
            end: Point | None = None,
            **qualifiers,
        ) -> Event:
            event = Event(
                id=str(uuid5(possession_id, f"event:{len(events)}")),
                match_id=self.match_id,
                minute=self.clock // 60,
                second=self.clock % 60,
                team_id=self.clubs[team].id,
                player_id=player.id,
                type=kind,
                start=start.model_copy(),
                end=end.model_copy() if end else None,
                distance=round(distance(start, end), 4) if end else None,
                angle=shot_angle(start)
                if kind == EventType.SHOT
                else (direction(start, end) if end else None),
                pitch_zone=pitch_zone(start),
                possession_id=str(possession_id),
                play_pattern=pattern,
                **qualifiers,
            )
            events.append(event)
            return event

        def advance() -> None:
            if phases[-1] == PossessionPhase.BUILD_UP and point.x >= 40:
                phases.append(PossessionPhase.PROGRESSION)
            if phases[-1] == PossessionPhase.PROGRESSION and point.x >= 70:
                phases.append(PossessionPhase.FINAL_THIRD)

        def finish(outcome: str, following: _Restart) -> tuple[PossessionFrame, _Restart]:
            phases.append(PossessionPhase.OUTCOME)
            return PossessionFrame(
                possession=Possession(
                    id=str(possession_id),
                    match_id=self.match_id,
                    team_id=club.id,
                    start_minute=began // 60,
                    start_second=began % 60,
                    end_minute=self.clock // 60,
                    end_second=self.clock % 60,
                    phase=PossessionPhase.OUTCOME,
                    outcome=outcome,
                    event_ids=[event.id for event in events],
                ),
                phases=phases,
                events=events,
            ), following

        # Restart actions are kept in their own possession, including set pieces.
        if restart.kind == EventType.CORNER:
            receiver = max(self._outfield(owner), key=lambda p: p.technical.finishing)
            target = Point(x=88, y=50)
            emit(owner, carrier, restart.kind, point, target, related_player_id=receiver.id)
            point, carrier = target, receiver
        else:
            emit(owner, carrier, restart.kind, point)
        advance()
        for _ in range(12):
            seconds = max(5, rng.randint(10, 21) - round((club.tactical_identity.tempo - 50) / 12))
            if self.clock + seconds >= period_end:
                self.clock = period_end
                return finish("period_end", restart)
            self.clock += seconds
            defender = rng.choices(
                self._outfield(opponent),
                weights=[p.mental.marking + p.physical.pace for p in self._outfield(opponent)],
                k=1,
            )[0]
            pressured = rng.random() < 0.15 + rival.tactical_identity.press_intensity / 160
            pressure = {
                "under_pressure": pressured,
                "pressured_by": defender.id if pressured else None,
            }
            if rng.random() < 0.025:
                emit(
                    opponent,
                    defender,
                    EventType.FOUL,
                    mirror(point),
                    related_player_id=carrier.id,
                    outcome=Outcome.FAIL,
                )
                return finish("foul_won", _Restart(owner, EventType.FREE_KICK, point))
            if phases[-1] == PossessionPhase.FINAL_THIRD and rng.random() < 0.55:
                keeper = self._keeper(opponent)
                xg = shot_value(point)
                chance = min(
                    0.8,
                    max(
                        0.005,
                        xg
                        * (0.65 + carrier.technical.finishing / 140)
                        * (1 - keeper.goalkeeping.reflexes / 400)
                        * (1 - fatigue(carrier, self.clock / 60) / 200)
                        * (0.85 if pressured else 1),
                    ),
                )
                draw = rng.random()
                result = (
                    ShotOutcome.GOAL
                    if draw < chance
                    else rng.choices(
                        [ShotOutcome.SAVED, ShotOutcome.BLOCKED, ShotOutcome.OFF_TARGET],
                        weights=[45, 25, 30],
                        k=1,
                    )[0]
                )
                target = Point(x=100, y=rng.uniform(45, 55))
                if result == ShotOutcome.OFF_TARGET:
                    target = Point(x=100, y=rng.choice([35, 65]))
                if pressured:
                    emit(
                        opponent,
                        defender,
                        EventType.PRESS,
                        mirror(point),
                        related_player_id=carrier.id,
                        outcome=Outcome.FAIL,
                    )
                body = (
                    BodyPart.LEFT_FOOT
                    if carrier.preferred_foot == Foot.LEFT
                    else BodyPart.RIGHT_FOOT
                )
                if pattern == PlayPattern.FROM_CORNER and rng.random() < 0.4:
                    body = BodyPart.HEAD
                shot = emit(
                    owner,
                    carrier,
                    EventType.SHOT,
                    point,
                    target,
                    expected_value=xg,
                    shot_outcome=result,
                    body_part=body,
                    outcome=Outcome.SUCCESS if result == ShotOutcome.GOAL else Outcome.FAIL,
                    **pressure,
                )
                if result == ShotOutcome.GOAL:
                    emit(
                        owner,
                        carrier,
                        EventType.GOAL,
                        point,
                        target,
                        subtype=f"from_shot:{shot.id}",
                        body_part=body,
                    )
                    return finish("goal", _Restart(opponent, EventType.KICKOFF, Point(x=50, y=50)))
                if result == ShotOutcome.SAVED:
                    emit(
                        opponent,
                        keeper,
                        EventType.SAVE,
                        mirror(target),
                        related_player_id=carrier.id,
                    )
                    return finish(
                        "saved", _Restart(opponent, EventType.GOAL_KICK, Point(x=8, y=50))
                    )
                if result == ShotOutcome.BLOCKED:
                    emit(
                        opponent,
                        defender,
                        EventType.BLOCK,
                        mirror(point),
                        related_player_id=carrier.id,
                    )
                    if rng.random() < 0.65:
                        return finish(
                            "corner",
                            _Restart(owner, EventType.CORNER, Point(x=99, y=rng.choice([0, 100]))),
                        )
                    return finish(
                        "blocked",
                        _Restart(opponent, EventType.RECOVERY, mirror(point), defender.id),
                    )
                return finish(
                    "off_target", _Restart(opponent, EventType.GOAL_KICK, Point(x=8, y=50))
                )

            kind = rng.choices([EventType.PASS, EventType.CARRY, EventType.DRIBBLE], [72, 20, 8])[0]
            direct = club.tactical_identity.build_up == BuildUpStyle.DIRECT
            step = rng.uniform(16, 34) if direct and kind == EventType.PASS else rng.uniform(7, 19)
            if not direct and rng.random() < 0.2:
                step = rng.uniform(-5, 4)
            target = Point(
                x=max(3, min(96, point.x + step)),
                y=max(
                    4, min(96, point.y + rng.uniform(-18, 18) * club.tactical_identity.width / 60)
                ),
            )
            receiver = carrier
            if kind == EventType.PASS:
                candidates = [p for p in self._outfield(owner) if p.id != carrier.id]
                receiver = rng.choice(candidates)
            completed = rng.random() < action_probability(
                carrier, kind, distance(point, target), self.clock / 60, pressured
            )
            if pressured:
                emit(
                    opponent,
                    defender,
                    EventType.PRESS,
                    mirror(point),
                    related_player_id=carrier.id,
                    outcome=Outcome.FAIL if completed else Outcome.SUCCESS,
                )
            emit(
                owner,
                carrier,
                kind,
                point,
                target,
                subtype="long" if direct and kind == EventType.PASS else None,
                related_player_id=receiver.id
                if kind == EventType.PASS
                else (defender.id if kind == EventType.DRIBBLE and pressured else None),
                progressive=target.x - point.x >= 10,
                outcome=Outcome.SUCCESS if completed else Outcome.FAIL,
                **pressure,
            )
            if not completed:
                return finish(
                    "turnover", _Restart(opponent, EventType.RECOVERY, mirror(target), defender.id)
                )
            point, carrier = target, receiver
            advance()
        # Bound long sequences with an explicit clearance, not a silent ownership flip.
        target = Point(x=96, y=50)
        emit(owner, carrier, EventType.CLEARANCE, point, target)
        return finish("clearance", _Restart(opponent, EventType.RECOVERY, mirror(target)))

    def frames(self) -> Iterator[PossessionFrame]:
        half = self.config.duration_minutes * 30
        for period in range(2):
            self.clock = period * half
            restart = _Restart(period, EventType.KICKOFF, Point(x=50, y=50))
            period_end = (period + 1) * half
            while self.clock < period_end:
                frame, restart = self._possession(restart, period_end)
                yield frame
                # Stoppage/reset time, deliberately outside possession duration.
                self.clock = min(period_end, self.clock + 8)


def iter_possessions(
    home: Club,
    away: Club,
    config: MatchConfig | None = None,
) -> Iterator[PossessionFrame]:
    return _Match(home, away, config or MatchConfig()).frames()


def iter_events(home: Club, away: Club, config: MatchConfig | None = None) -> Iterator[Event]:
    for frame in iter_possessions(home, away, config):
        yield from frame.events


def simulate_match(home: Club, away: Club, config: MatchConfig | None = None) -> MatchResult:
    from tactix.simulation.validation import validate_match

    match = _Match(home, away, config or MatchConfig())
    result = MatchResult(
        match_id=match.match_id,
        home_club_id=home.id,
        away_club_id=away.id,
        config=match.config,
        frames=list(match.frames()),
    )
    validate_match(result, home, away)
    return result
