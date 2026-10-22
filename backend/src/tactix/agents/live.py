"""Run the two real MAF/Foundry specialists on a fixed authored-demo cut."""

import argparse
import asyncio
import importlib.metadata
import json
from pathlib import Path

from tactix.agents.foundry import require_foundry_configuration, run_specialists
from tactix.agents.tools import EvidenceTools
from tactix.config import Settings
from tactix.demo.scenario import build_demo


async def execute(settings, second):
    bundle = build_demo()
    scope = EvidenceTools(
        bundle.live, bundle.league, second, historical_matches=bundle.historical_matches
    )
    return await run_specialists(scope, settings)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at-second", type=int, default=3720)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--check-config", action="store_true", help="Safe local diagnostics; no inference"
    )
    args = parser.parse_args()
    try:
        settings = Settings()
        if args.check_config:
            packages = {}
            for package in ("agent-framework-core", "agent-framework-foundry"):
                try:
                    packages[package] = importlib.metadata.version(package)
                except importlib.metadata.PackageNotFoundError:
                    packages[package] = None
            print(
                json.dumps(
                    {
                        "endpoint_configured": bool(settings.foundry_endpoint),
                        "deployment_configured": bool(settings.foundry_model),
                        "authentication": settings.foundry_authentication,
                        "packages": packages,
                        "live_verified": False,
                    }
                )
            )
            return
        if args.output is None:
            parser.error("Provide --output for live execution")
        require_foundry_configuration(settings)
        if args.output.exists():
            raise ValueError("Output file already exists")
        if not 0 <= args.at_second <= 5400:
            raise ValueError("at-second must be between 0 and 5400")
        result = asyncio.run(execute(settings, args.at_second))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as destination:
            destination.write(result.model_dump_json(indent=2) + "\n")
        if result.partial:
            parser.exit(
                2, "Specialist run degraded; inspect failure codes in the output artifact.\n"
            )
    except ImportError:
        parser.error("Install the agents extra with uv sync --extra agents")
    except (ValueError, OSError):
        parser.error("Check Foundry configuration, cutoff and a new writable output path")


if __name__ == "__main__":
    main()
