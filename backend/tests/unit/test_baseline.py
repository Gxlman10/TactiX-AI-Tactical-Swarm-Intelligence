import json

from tactix.agents.baseline import BASELINE_VERSION, build_baseline_request
from tactix.agents.contracts import Preferences
from tactix.agents.tools import EvidenceTools
from tactix.demo.scenario import build_demo


def test_baseline_uses_the_same_frozen_cut_without_tools():
    bundle = build_demo()
    scope = EvidenceTools(
        bundle.live,
        bundle.league,
        3720,
        historical_matches=bundle.historical_matches,
    )
    request = build_baseline_request(
        scope,
        Preferences(focus_player_id=next(iter(scope.players))),
    )
    payload = json.loads(request["messages"][1]["content"])

    assert request["baseline_version"] == BASELINE_VERSION
    assert request["tools"] == []
    assert payload["match_id"] == scope.match_id
    assert payload["at_second"] == 3720
    assert payload["revision"] == scope.revision
    assert payload["visible_events"]
    assert payload["metrics"]["match_id"] == scope.match_id
    assert request["output_schema"]["title"] == "NarratorOutput"
