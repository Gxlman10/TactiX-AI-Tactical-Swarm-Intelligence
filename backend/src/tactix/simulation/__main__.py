"""Export a reproducible match artifact or ordered Event JSONL stream."""

import argparse
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tactix.simulation.engine import MatchConfig, simulate_match
from tactix.universe.generator import LeagueConfig, generate_league


class MatchScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    league: LeagueConfig = Field(default_factory=LeagueConfig)
    match: MatchConfig = Field(default_factory=MatchConfig)
    home: str = "Ashford"
    away: str = "Northbridge"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--seed", type=int, help="Override the match seed, keeping league inputs")
    parser.add_argument("--duration-minutes", type=int)
    parser.add_argument("--home")
    parser.add_argument("--away")
    parser.add_argument("--format", choices=("json", "jsonl"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        scenario = (
            MatchScenario.model_validate_json(args.config.read_text(encoding="utf-8"))
            if args.config
            else MatchScenario()
        )
        overrides = {
            key: getattr(args, key)
            for key in ("seed", "duration_minutes")
            if getattr(args, key) is not None
        }
        config = MatchConfig.model_validate(scenario.match.model_dump() | overrides)
        league = generate_league(scenario.league)
        selections = [args.home or scenario.home, args.away or scenario.away]
        selected = []
        for selection in selections:
            matches = [club for club in league.clubs if selection in (club.id, club.name)]
            if len(matches) != 1:
                raise ValueError(f"Expected one club matching {selection!r}")
            selected.append(matches[0])
        result = simulate_match(*selected, config=config)
        output = (
            result.model_dump_json(indent=2)
            if args.format == "json"
            else "\n".join(event.model_dump_json() for event in result.events)
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(output + "\n")
        else:
            print(output)
    except (OSError, ValueError, ValidationError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
