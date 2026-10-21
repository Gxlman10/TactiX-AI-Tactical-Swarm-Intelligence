"""Domain contracts — the single source of truth every layer builds against.

Frozen on day 1 so the layers can be developed in parallel against the schema, not against
each other's code.
"""

from tactix.domain.agents import (
    Conflict,
    Finding,
    MatchContext,
    MatchReport,
    Narration,
    NarrationMoment,
    Personalization,
    PersonalizedView,
)
from tactix.domain.common import Point, Rating
from tactix.domain.enums import (
    AgentName,
    BodyPart,
    BuildUpStyle,
    CardType,
    EventType,
    Foot,
    Frame,
    Language,
    Outcome,
    PlayPattern,
    Position,
    PossessionPhase,
    ShotOutcome,
    ViewMode,
)
from tactix.domain.events import Event, Possession
from tactix.domain.metrics import (
    Evidence,
    MetricsSnapshot,
    MetricValue,
    PassNetwork,
    PassNetworkEdge,
    PassNetworkNode,
    PlayerRating,
    ShotMapEntry,
    TeamMetrics,
)
from tactix.domain.universe import (
    Club,
    Fixture,
    HeadToHead,
    League,
    Player,
    StandingRow,
    TacticalIdentity,
)

__all__ = [
    # common / enums
    "Point",
    "Rating",
    "AgentName",
    "BodyPart",
    "BuildUpStyle",
    "CardType",
    "EventType",
    "Foot",
    "Frame",
    "Language",
    "Outcome",
    "PlayPattern",
    "Position",
    "PossessionPhase",
    "ShotOutcome",
    "ViewMode",
    # universe
    "Club",
    "Fixture",
    "HeadToHead",
    "League",
    "Player",
    "StandingRow",
    "TacticalIdentity",
    # events
    "Event",
    "Possession",
    # metrics
    "Evidence",
    "MetricValue",
    "MetricsSnapshot",
    "PassNetwork",
    "PassNetworkEdge",
    "PassNetworkNode",
    "PlayerRating",
    "ShotMapEntry",
    "TeamMetrics",
    # agents / blackboard
    "Conflict",
    "Finding",
    "MatchContext",
    "MatchReport",
    "Narration",
    "NarrationMoment",
    "Personalization",
    "PersonalizedView",
]
