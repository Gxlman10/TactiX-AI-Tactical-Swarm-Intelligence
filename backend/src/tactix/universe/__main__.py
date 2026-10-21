"""Export a reproducible league without requiring PostgreSQL or a model service."""

import argparse
from pathlib import Path

from pydantic import ValidationError

from tactix.universe.generator import LeagueConfig, generate_league


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Versioned league configuration JSON")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--clubs", type=int, dest="club_count")
    parser.add_argument("--season")
    parser.add_argument("--generator-version", choices=("league-v1", "league-v2", "league-v3"))
    parser.add_argument("--matchdays", type=int, dest="history_matchdays")
    parser.add_argument("--output", type=Path, help="Write JSON to a new file instead of stdout")
    args = parser.parse_args()
    try:
        base = (
            LeagueConfig.model_validate_json(args.config.read_text(encoding="utf-8"))
            if args.config
            else LeagueConfig()
        )
        overrides = {
            key: getattr(args, key)
            for key in ("seed", "club_count", "season", "generator_version", "history_matchdays")
            if getattr(args, key) is not None
        }
        config = LeagueConfig.model_validate(base.model_dump() | overrides)
        output = generate_league(config).model_dump_json(indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as target:
                target.write(output)
        else:
            print(output, end="")
    except (OSError, ValidationError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
