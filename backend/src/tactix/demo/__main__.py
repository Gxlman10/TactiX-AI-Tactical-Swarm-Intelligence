"""Export the versioned Ashford scenario and its reproducible evidence bundle."""

import argparse
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from tactix.demo.scenario import build_demo, demo_context


class DemoManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    scenario_version: Literal["ashford-demo-v1"] = "ashford-demo-v1"
    base_league_seed: Literal[42] = 42
    base_match_seed: Literal[42] = 42
    history_matchdays: Literal[12] = 12
    duration_minutes: Literal[90] = 90
    climax_second: Literal[3720] = 3720


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="Must be a new directory")
    args = parser.parse_args()
    try:
        DemoManifest.model_validate_json(args.config.read_text(encoding="utf-8"))
        bundle = build_demo()
        args.output_dir.mkdir(parents=True, exist_ok=False)
        artifacts = {
            "bundle.json": bundle,
            "league.json": bundle.league,
            "match.json": bundle.live,
            "context-62.json": demo_context(bundle, 3720),
        }
        for name, artifact in artifacts.items():
            with (args.output_dir / name).open("x", encoding="utf-8") as destination:
                destination.write(artifact.model_dump_json(indent=2) + "\n")
        print(f"Exported {bundle.scenario_version} to {args.output_dir}")
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
