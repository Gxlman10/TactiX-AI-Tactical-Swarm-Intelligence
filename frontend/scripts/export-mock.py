"""Export a small UI rehearsal from validated synthetic backend artifacts."""

import json
from pathlib import Path

from tactix.demo.scenario import build_demo, demo_context
from tactix.metrics.advanced import advanced_metrics_for_match

bundle = build_demo()
start, end = 3660, 3780
keys = {
    "possession_pct",
    "passes_attempted",
    "pass_accuracy_pct",
    "shots",
    "goals",
    "xg_like",
    "field_tilt",
}
snapshots = {}
for second in range(start, end + 1):
    snapshot = advanced_metrics_for_match(bundle.live, second)
    snapshots[str(second)] = [
        {v.key: v.value for v in team.values if v.key in keys} for team in snapshot.teams
    ]
payload = {
    "version": "rehearsal-v1",
    "scenario": bundle.scenario_version,
    "match_id": bundle.live.match_id,
    "season": bundle.league.season,
    "start": start,
    "end": end,
    "initial": 3720,
    "teams": [
        {
            "id": club.id,
            "name": club.name,
            "city": club.city,
            "formation": club.tactical_identity.formation,
            "players": [{"id": p.id, "name": p.name, "number": p.number} for p in club.squad],
        }
        for key in (bundle.live.home_club_id, bundle.live.away_club_id)
        for club in bundle.league.clubs
        if club.id == key
    ],
    "events": [
        e.model_dump(mode="json")
        for e in bundle.live.events
        if start <= e.minute * 60 + e.second <= end
    ],
    "snapshots": snapshots,
    "context": demo_context(bundle, 3720).model_dump(mode="json"),
}
output = Path(__file__).resolve().parents[1] / "src/features/match/fixture.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Exported {len(payload['events'])} synthetic events and {len(snapshots)} exact cuts")
