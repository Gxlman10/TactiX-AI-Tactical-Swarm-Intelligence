"""Layer 2 inputs: the match event stream and the possession chains that link it.

Events carry pitch coordinates and qualifiers so the metrics engine can compute spatial and
sequence-aware statistics, not just flat counts.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tactix.domain.common import Point
from tactix.domain.enums import (
    BodyPart,
    CardType,
    EventType,
    Outcome,
    PlayPattern,
    PossessionPhase,
    ShotOutcome,
)


class Event(BaseModel):
    id: str
    match_id: str
    minute: int = Field(ge=0)
    second: int = Field(default=0, ge=0, le=59)
    team_id: str
    player_id: str
    type: EventType
    subtype: str | None = None  # e.g. "through_ball", "switch", "line_breaking"

    start: Point
    end: Point | None = None

    outcome: Outcome = Outcome.SUCCESS
    body_part: BodyPart | None = None
    under_pressure: bool = False
    pressured_by: str | None = None  # player_id applying the pressure
    play_pattern: PlayPattern = PlayPattern.OPEN_PLAY
    progressive: bool = False
    distance: float | None = None
    angle: float | None = None
    pitch_zone: int | None = Field(default=None, ge=1, le=18)  # thirds x channels grid

    possession_id: str | None = None
    related_player_id: str | None = None  # receiver, or the beaten defender

    expected_value: float | None = None  # xG / xT / xA-like, deterministic zone weight
    shot_outcome: ShotOutcome | None = None
    card_type: CardType | None = None


class Possession(BaseModel):
    id: str
    match_id: str
    team_id: str
    start_minute: int
    start_second: int = 0
    end_minute: int
    end_second: int = 0
    phase: PossessionPhase = PossessionPhase.BUILD_UP
    event_ids: list[str] = Field(default_factory=list)
    outcome: str = ""  # "shot", "turnover", "foul_won", "set_piece", ...
