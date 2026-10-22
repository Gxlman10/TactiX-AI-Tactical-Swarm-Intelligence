"""Export swarm-contracts-v1 prompts, role boundaries and JSON schemas; no model calls."""

import argparse
import hashlib
import json
from pathlib import Path

from tactix.agents.contracts import CONTRACT_VERSION, SPECS
from tactix.agents.tools import TOOL_ARGUMENTS


def specification() -> dict:
    agents = []
    for spec in SPECS.values():
        prompt = spec.prompt()
        agents.append(
            {
                "agent": spec.agent.value,
                "reads": list(spec.reads),
                "writes": list(spec.writes),
                "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "output_schema": spec.output.model_json_schema(),
                "tools": [
                    {
                        "name": name,
                        "description": TOOL_ARGUMENTS[name][1],
                        "parameters": TOOL_ARGUMENTS[name][0].model_json_schema(),
                    }
                    for name in spec.tools
                ],
            }
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "model_execution": False,
        "agents": agents,
        "stages": [
            ["tactical_analyst", "historian"],
            ["orchestrator:review"],
            ["narrator"],
            ["personalizer"],
            ["orchestrator:finalize"],
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = json.dumps(specification(), ensure_ascii=False, indent=2, allow_nan=False)
    try:
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(output + "\n")
        else:
            print(output)
    except OSError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
