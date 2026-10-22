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
    parser.add_argument(
        "--advanced", action="store_true", help="Include advanced-v1 spatial metrics"
    )
    args = parser.parse_args()
    try:
        result = MatchResult.model_validate_json(args.input.read_text(encoding="utf-8"))
        cutoff = (
            args.at_second if args.at_second is not None else result.config.duration_minutes * 60
        )
        version = METRICS_VERSION
        compute = metrics_for_match
        if args.advanced:
            from tactix.metrics.advanced import METRICS_VERSION as advanced_version
            from tactix.metrics.advanced import advanced_metrics_for_match

            version, compute = advanced_version, advanced_metrics_for_match
        snapshot = compute(result, cutoff)
        output = json.dumps(
            {
                "metrics_version": version,
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
