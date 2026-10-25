"""Run the full swarm workflow on the authored demo cut and write the assembled report.

Live execution needs a configured Foundry project (the Narrator and Personalizer call the
model); ``--check-config`` reports local readiness without any inference. The deterministic
orchestration — conflict detection, sequencing, degradation and report assembly — is covered
offline by tests/unit/test_workflow_orchestration.py.
"""

import argparse
import asyncio
import json
from pathlib import Path

from tactix.agents.contracts import Preferences
from tactix.agents.providers import get_provider
from tactix.agents.tools import EvidenceTools
from tactix.config import Settings
from tactix.demo.scenario import build_demo
from tactix.domain.enums import Language
from tactix.workflows.orchestration import WORKFLOW_VERSION, run_match_report


async def execute(settings: Settings, second: int, preferences: Preferences):
    bundle = build_demo()
    scope = EvidenceTools(
        bundle.live, bundle.league, second, historical_matches=bundle.historical_matches
    )
    return await run_match_report(scope, settings, preferences)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at-second", type=int, default=3720)
    parser.add_argument("--language", choices=[lang.value for lang in Language], default="en")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--check-config", action="store_true", help="Safe local diagnostics; no inference"
    )
    args = parser.parse_args()
    try:
        settings = Settings()
        if args.check_config:
            print(
                json.dumps(
                    {
                        "workflow_version": WORKFLOW_VERSION,
                        "provider": settings.model_provider,
                        "endpoint_configured": bool(settings.foundry_endpoint),
                        "deployment_configured": bool(settings.foundry_model),
                        "authentication": settings.foundry_authentication,
                        "live_verified": False,
                    }
                )
            )
            return
        if args.output is None:
            parser.error("Provide --output for live execution")
        get_provider(settings).validate_configuration(settings)
        if args.output.exists():
            raise ValueError("Output file already exists")
        if not 0 <= args.at_second <= 5400:
            raise ValueError("at-second must be between 0 and 5400")
        preferences = Preferences(language=Language(args.language))
        result = asyncio.run(execute(settings, args.at_second, preferences))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as destination:
            destination.write(result.model_dump_json(indent=2) + "\n")
        if result.partial:
            parser.exit(2, "Workflow shipped partial; inspect degraded stages in the output.\n")
    except ImportError:
        parser.error("Install the agents extra with uv sync --extra agents")
    except (ValueError, OSError):
        parser.error("Check Foundry configuration, cutoff and a new writable output path")


if __name__ == "__main__":
    main()
