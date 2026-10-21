"""Layer 2 outputs: deterministic metrics with the evidence that produced them.

Every value is computed in code from events. The "expected" models (xG/xT/xA-like) are
deterministic zone-weight functions, not machine learning. Each value keeps the event ids it
was derived from so any claim can be traced back.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tactix.domain.common import Point
from tactix.domain.enums import ShotOutcome


class Evidence(BaseModel):
    """The traceable link from a number back to the events that produced it."""

    event_ids: list[str] = Field(default_factory=list)
    description: str = ""


class MetricValue(BaseModel):
    key: str  # machine key, e.g. "possession_pct", "ppda", "field_tilt"
    label: str  # human label, e.g. "Possession %"
    value: float
    unit: str | None = None
    evidence: Evidence = Field(default_factory=Evidence)


class PassNetworkNode(BaseModel):
    player_id: str
    touches: int = 0
    degree_centrality: float = 0.0
    betweenness_centrality: float = 0.0
    avg_location: Point | None = None


class PassNetworkEdge(BaseModel):
    from_player_id: str
    to_player_id: str
    passes: int = 0


class PassNetwork(BaseModel):
    team_id: str
    nodes: list[PassNetworkNode] = Field(default_factory=list)
    edges: list[PassNetworkEdge] = Field(default_factory=list)


class ShotMapEntry(BaseModel):
    event_id: str
    player_id: str
    location: Point
    xg: float
    outcome: ShotOutcome


class MomentumPoint(BaseModel):
    minute: int
    value: float  # signed: positive favours the home team, negative the away team


class PlayerRating(BaseModel):
    player_id: str
    rating: float = Field(ge=0, le=10)
    evidence: Evidence = Field(default_factory=Evidence)


class TeamMetrics(BaseModel):
    team_id: str
    values: list[MetricValue] = Field(default_factory=list)
    pass_network: PassNetwork | None = None
    shot_map: list[ShotMapEntry] = Field(default_factory=list)


class MetricsSnapshot(BaseModel):
    """The full deterministic read of a match up to ``minute``."""

    match_id: str
    minute: int = 0
    teams: list[TeamMetrics] = Field(default_factory=list)
    player_ratings: list[PlayerRating] = Field(default_factory=list)
    momentum: list[MomentumPoint] = Field(default_factory=list)
