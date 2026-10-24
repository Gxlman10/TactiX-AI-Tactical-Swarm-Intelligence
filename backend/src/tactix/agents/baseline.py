"""Single-agent baseline request used to compare against the specialist swarm.

The baseline intentionally receives the same frozen evidence cut but has one prompt, no
role-specific tools and no handoffs. It is a request builder, not a claim that inference has
already been run; Foundry credentials are still required to produce a live baseline output.
"""

import json

from tactix.agents.contracts import NarratorOutput, Preferences
from tactix.agents.tools import EvidenceTools

BASELINE_VERSION = "single-agent-baseline-v1"

BASELINE_PROMPT = """You are the single-agent baseline for TactiX.
Produce one concise, evidence-grounded football explanation from the supplied match cut.
You perform the tactical, historical and narrative reasoning in one pass. Do not claim facts
that are not in the input. Every play-by-play or key moment must cite existing evidence IDs;
if the evidence is insufficient, return an empty list rather than guessing. Return only JSON
matching the supplied NarratorOutput schema.
"""


def build_baseline_request(scope: EvidenceTools, preferences: Preferences | None = None) -> dict:
    """Build a tool-free single-agent request over the exact same visible evidence cut."""
    preferences = preferences or Preferences()
    visible_events = [event.model_dump(mode="json") for event in scope.live_events.values()]
    input_data = {
        "baseline_version": BASELINE_VERSION,
        "match_id": scope.match_id,
        "at_second": scope.at_second,
        "revision": scope.revision,
        "preferences": preferences.model_dump(mode="json"),
        "metrics": scope.metrics().model_dump(mode="json"),
        "visible_events": visible_events,
        "historical_fixtures": [
            fixture.model_dump(mode="json") for fixture in scope.fixtures.values()
        ],
    }
    return {
        "baseline_version": BASELINE_VERSION,
        "agent": "single_agent_baseline",
        "tools": [],
        "messages": [
            {"role": "system", "content": BASELINE_PROMPT},
            {"role": "user", "content": json.dumps(input_data, ensure_ascii=False)},
        ],
        "output_schema": NarratorOutput.model_json_schema(),
    }
