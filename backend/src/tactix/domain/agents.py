"""Layer 3 contracts: the shared blackboard the swarm reads and writes.

The flow is fan-out / fan-in: Tactical Analyst and Historian run in parallel over the metrics
and universe, the Narrator fans their findings in, the Personalizer adapts the result, and the
Orchestrator supervises — detecting conflicts and recording which agents degraded.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tactix.domain.enums import AgentName, Frame, Language, ViewMode
from tactix.domain.metrics import Evidence, MetricsSnapshot


class Finding(BaseModel):
    id: str
    agent: AgentName
    moment_minute: int
    frame: Frame
    claim: str
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence = Field(default_factory=Evidence)
    references: list[str] = Field(default_factory=list)  # fixture ids / historical refs


class Conflict(BaseModel):
    """A genuine disagreement anchored to the same moment, surfaced rather than hidden."""

    moment_minute: int
    analyst_finding_id: str
    historian_finding_id: str
    resolution: str  # how the Orchestrator presented both readings


class NarrationMoment(BaseModel):
    minute: int
    text: str
    source_finding_ids: list[str] = Field(default_factory=list)  # provenance for the UI


class Narration(BaseModel):
    play_by_play: list[NarrationMoment] = Field(default_factory=list)
    recap: str = ""
    key_moments: list[NarrationMoment] = Field(default_factory=list)


class PersonalizedView(BaseModel):
    mode: ViewMode
    language: Language
    content: str


class Personalization(BaseModel):
    language: Language = Language.EN
    favourite_club_id: str | None = None
    focus_player_id: str | None = None
    views: list[PersonalizedView] = Field(default_factory=list)


class MatchContext(BaseModel):
    """The shared state object passed through the workflow."""

    match_id: str
    minute: int = 0
    metrics: MetricsSnapshot | None = None
    analyst_findings: list[Finding] = Field(default_factory=list)
    historian_findings: list[Finding] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    narration: Narration | None = None
    personalization: Personalization | None = None
    degraded: list[AgentName] = Field(default_factory=list)  # agents unavailable this run


class MatchReport(BaseModel):
    """What the Orchestrator ships. ``partial`` is True when any agent degraded."""

    match_id: str
    minute: int
    narration: Narration | None = None
    personalization: Personalization | None = None
    conflicts: list[Conflict] = Field(default_factory=list)
    degraded: list[AgentName] = Field(default_factory=list)
    partial: bool = False
