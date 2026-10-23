"""Layer 3 — Microsoft Agent Framework fan-out/fan-in workflow, shared state, recovery.

Owner: R3.
"""

from tactix.workflows.orchestration import (
    WORKFLOW_VERSION,
    MatchReportRun,
    StageOutcome,
    detect_conflicts,
    run_match_report,
)

__all__ = [
    "WORKFLOW_VERSION",
    "MatchReportRun",
    "StageOutcome",
    "detect_conflicts",
    "run_match_report",
]
