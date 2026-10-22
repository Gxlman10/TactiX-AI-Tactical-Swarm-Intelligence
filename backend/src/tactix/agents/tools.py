"""Role-scoped, read-only evidence tools at an immutable football-time cut."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tactix.agents.contracts import SPECS
from tactix.demo.evidence import midfield_concessions, seconds
from tactix.domain.enums import AgentName, EventType
from tactix.domain.universe import League
from tactix.metrics.advanced import advanced_metrics_for_match
from tactix.simulation.engine import MatchResult
from tactix.simulation.validation import validate_match
from tactix.universe.history import validate_history

Identifier = Annotated[str, Field(min_length=1, max_length=150)]


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EventQuery(Arguments):
    event_ids: list[Identifier] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError("Event IDs must be unique")
        return self


class ClubQuery(Arguments):
    club_id: Identifier


class PlayerQuery(Arguments):
    player_id: Identifier


class FixtureQuery(ClubQuery):
    opponent_id: Identifier | None = None
    limit: int = Field(default=5, ge=1, le=20)
    fixture_ids: list[Identifier] | None = Field(default=None, min_length=1, max_length=20)


TOOL_ARGUMENTS = {
    "read_metrics": (Arguments, "Read computed advanced-v1 metrics at this exact visible cut."),
    "read_events": (EventQuery, "Resolve supplied IDs; unknown or future IDs fail atomically."),
    "read_club": (ClubQuery, "Read the fictional club roster and authored tactical profile."),
    "read_player": (PlayerQuery, "Read a fictional player's recorded attributes, not tracking."),
    "read_fixtures": (FixtureQuery, "Read recent or selected recorded fixtures, newest first."),
    "player_goals": (
        PlayerQuery,
        "Read code-counted season goals with fixture/live-event sources.",
    ),
    "read_patterns": (ClubQuery, "Read event-backed midfield concessions; unaudited is unknown."),
}


class EvidenceTools:
    def __init__(
        self,
        result: MatchResult,
        league: League,
        at_second: int,
        *,
        revision: int = 0,
        historical_matches: dict[str, MatchResult] | None = None,
    ):
        if type(revision) is not int or revision < 0:
            raise ValueError("revision must be a nonnegative integer")
        validate_history(league)
        clubs = {c.id: c for c in league.clubs}
        validate_match(result, clubs[result.home_club_id], clubs[result.away_club_id])
        self._metrics = advanced_metrics_for_match(result, at_second)
        self.match_id, self.at_second, self.revision = result.match_id, at_second, revision
        self._result = result.model_copy(deep=True)
        self._league = league.model_copy(deep=True)
        self.clubs = {c.id: c for c in self._league.clubs}
        self.players = {p.id: p for c in self.clubs.values() for p in c.squad}
        self.fixtures = {f.id: f for f in self._league.fixtures}
        self.live_events = {e.id: e for e in self._result.events if seconds(e) <= at_second}
        self.historical_events = {}
        self.historical_owner: dict[str, str] = {}
        self._history = {}
        for key, match in (historical_matches or {}).items():
            fixture = self.fixtures.get(key)
            if (
                fixture is None
                or key != match.match_id
                or (
                    fixture.home_club_id,
                    fixture.away_club_id,
                    fixture.home_goals,
                    fixture.away_goals,
                )
                != (match.home_club_id, match.away_club_id, *match.score)
            ):
                raise ValueError("Historical artifact must match its recorded fixture")
            validate_match(match, self.clubs[match.home_club_id], self.clubs[match.away_club_id])
            copied = match.model_copy(deep=True)
            for event in copied.events:
                if event.id in self.live_events or event.id in self.historical_events:
                    raise ValueError("Evidence IDs must be globally unique")
                self.historical_events[event.id] = event
                self.historical_owner[event.id] = key
            self._history[key] = copied

    def schemas(self, agent: AgentName) -> list[dict]:
        return [
            {
                "name": name,
                "description": TOOL_ARGUMENTS[name][1],
                "parameters": TOOL_ARGUMENTS[name][0].model_json_schema(),
            }
            for name in SPECS[agent].tools
        ]

    def metrics(self):
        return self._metrics.model_copy(deep=True)

    def invoke(self, agent: AgentName, tool: str, arguments: dict) -> dict:
        if tool not in SPECS[agent].tools:
            raise PermissionError(f"{agent} cannot invoke {tool}")
        query = TOOL_ARGUMENTS[tool][0].model_validate(arguments)
        if isinstance(query, ClubQuery) and query.club_id not in self.clubs:
            raise ValueError("Unknown club ID")
        if isinstance(query, PlayerQuery) and query.player_id not in self.players:
            raise ValueError("Unknown player ID")
        if tool == "read_metrics":
            data = self._metrics.model_dump(mode="json")
        elif tool == "read_events":
            allowed = dict(self.live_events)
            if agent == AgentName.HISTORIAN:
                allowed.update(self.historical_events)
            if any(key not in allowed for key in query.event_ids):
                raise ValueError("Unknown, future or unauthorized event ID")
            data = [allowed[key].model_dump(mode="json") for key in query.event_ids]
        elif tool == "read_club":
            data = self.clubs[query.club_id].model_dump(mode="json")
        elif tool == "read_player":
            data = self.players[query.player_id].model_dump(mode="json")
        elif tool == "read_fixtures":
            if query.opponent_id is not None and query.opponent_id not in self.clubs:
                raise ValueError("Unknown opponent ID")
            candidates = [
                f
                for f in self.fixtures.values()
                if query.club_id in (f.home_club_id, f.away_club_id)
                and (
                    query.opponent_id is None
                    or query.opponent_id in (f.home_club_id, f.away_club_id)
                )
            ]
            if query.fixture_ids is not None:
                if (
                    len(set(query.fixture_ids)) != len(query.fixture_ids)
                    or len(query.fixture_ids) > query.limit
                    or not set(query.fixture_ids) <= {f.id for f in candidates}
                ):
                    raise ValueError("Requested fixture IDs must fit the query and limit")
                candidates = [f for f in candidates if f.id in query.fixture_ids]
            data = [
                f.model_dump(mode="json")
                for f in sorted(candidates, key=lambda f: (f.matchday, f.id), reverse=True)[
                    : query.limit
                ]
            ]
        elif tool == "player_goals":
            historical = [
                {"fixture_id": f.id, "minute": s.minute, "club_id": s.club_id}
                for f in self.fixtures.values()
                for s in f.scorers
                if s.player_id == query.player_id
            ]
            live = [
                e.id
                for e in self.live_events.values()
                if e.type == EventType.GOAL and e.player_id == query.player_id
            ]
            data = {
                "player_id": query.player_id,
                "goals": len(historical) + len(live),
                "historical_goals": historical,
                "live_goal_event_ids": live,
            }
        else:
            history = {
                key: [p.model_dump(mode="json") for p in midfield_concessions(match, query.club_id)]
                for key, match in self._history.items()
                if query.club_id in (match.home_club_id, match.away_club_id)
            }
            current = (
                [
                    p.model_dump(mode="json")
                    for p in midfield_concessions(self._result, query.club_id, self.at_second)
                ]
                if query.club_id in (self._result.home_club_id, self._result.away_club_id)
                else []
            )
            data = {
                "historical": history,
                "live": current,
                "coverage": "Only supplied historical event artifacts are audited; "
                "missing fixtures are unknown for this pattern.",
            }
        return {
            "match_id": self.match_id,
            "at_second": self.at_second,
            "revision": self.revision,
            "tool": tool,
            "data": data,
        }
