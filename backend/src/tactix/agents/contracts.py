"""Versioned agent boundaries around the unchanged shared domain contracts."""

from dataclasses import dataclass
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict

from tactix.domain.agents import Conflict, Finding, MatchReport, Narration, Personalization
from tactix.domain.enums import AgentName, Language

CONTRACT_VERSION = "swarm-contracts-v1"


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Preferences(BoundaryModel):
    language: Language = Language.EN
    favourite_club_id: str | None = None
    focus_player_id: str | None = None


class FindingsOutput(BoundaryModel):
    findings: list[Finding]


class NarratorOutput(BoundaryModel):
    narration: Narration


class PersonalizerOutput(BoundaryModel):
    personalization: Personalization


class OrchestratorOutput(BoundaryModel):
    conflicts: list[Conflict]
    report: MatchReport | None = None


@dataclass(frozen=True)
class AgentSpec:
    agent: AgentName
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    tools: tuple[str, ...]
    output: type[BaseModel]

    def prompt(self) -> str:
        root = files("tactix.agents.prompts")
        return (
            root.joinpath("common.md").read_text(encoding="utf-8")
            + "\n\n"
            + root.joinpath(f"{self.agent.value}.md").read_text(encoding="utf-8")
        )


SPECS = {
    AgentName.TACTICAL_ANALYST: AgentSpec(
        AgentName.TACTICAL_ANALYST,
        ("metrics",),
        ("analyst_findings",),
        ("read_metrics", "read_events"),
        FindingsOutput,
    ),
    AgentName.HISTORIAN: AgentSpec(
        AgentName.HISTORIAN,
        ("metrics", "universe"),
        ("historian_findings",),
        (
            "read_metrics",
            "read_events",
            "read_club",
            "read_player",
            "read_fixtures",
            "player_goals",
            "read_patterns",
        ),
        FindingsOutput,
    ),
    AgentName.NARRATOR: AgentSpec(
        AgentName.NARRATOR,
        ("analyst_findings", "historian_findings", "conflicts", "degraded"),
        ("narration",),
        (),
        NarratorOutput,
    ),
    AgentName.PERSONALIZER: AgentSpec(
        AgentName.PERSONALIZER,
        ("narration", "preferences", "degraded"),
        ("personalization",),
        (),
        PersonalizerOutput,
    ),
    AgentName.ORCHESTRATOR: AgentSpec(
        AgentName.ORCHESTRATOR,
        ("context", "preferences", "phase"),
        ("conflicts", "report"),
        (),
        OrchestratorOutput,
    ),
}

Phase = Literal["review", "finalize"]
