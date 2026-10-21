"""Compute core metrics from a complete simulation JSON artifact."""

import argparse
import json
from pathlib import Path

from tactix.metrics.core import METRICS_VERSION, metrics_for_match
from tactix.simulation.engine import MatchResult


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, required=True, help="Full MatchResult JSON, not JSONL"
    )
    parser.add_argument("--at-second", type=int, help="Inclusive match-time cutoff")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = MatchResult.model_validate_json(args.input.read_text(encoding="utf-8"))
        cutoff = (
            args.at_second if args.at_second is not None else result.config.duration_minutes * 60
        )
        snapshot = metrics_for_match(result, cutoff)
        output = json.dumps(
            {
                "metrics_version": METRICS_VERSION,
                "at_second": cutoff,
                "snapshot": snapshot.model_dump(mode="json"),
            },
            indent=2,
            ensure_ascii=False,
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(output + "\n")
        else:
            print(output)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
