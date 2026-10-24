"""Portable authored demo recording. No network, database or inference required."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from tactix.demo.evidence import seconds
from tactix.demo.scenario import DemoBundle, DemoContext, build_demo, demo_context
from tactix.domain.enums import EventType
from tactix.domain.metrics import MetricsSnapshot
from tactix.metrics.advanced import AdvancedMetrics
from tactix.simulation.replay import MatchReplay
from tactix.simulation.validation import validate_match
from tactix.universe.history import validate_history

CUTS = (3660, 3699, 3700, 3708, 3719, 3720, 3728, 3780, 5400)
PAYLOAD = "recording.json.gz"
MAX_BYTES = 32 * 1024 * 1024


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Checkpoint(FrozenModel):
    at_second: int
    score: tuple[int, int]
    visible_event_ids: list[str]
    metrics: MetricsSnapshot
    context: DemoContext


class Recording(FrozenModel):
    format_version: Literal["tactix-recording-v1"] = "tactix-recording-v1"
    source_kind: Literal["authored-synthetic"] = "authored-synthetic"
    agent_inference: Literal[False] = False
    bundle: DemoBundle
    checkpoints: list[Checkpoint]


class Manifest(FrozenModel):
    format_version: Literal["tactix-recording-v1"] = "tactix-recording-v1"
    scenario_version: Literal["ashford-demo-v1"] = "ashford-demo-v1"
    payload: Literal["recording.json.gz"] = PAYLOAD
    sha256: str
    canonical_bytes: int
    match_id: str
    event_count: int
    historical_fixture_ids: list[str]
    checkpoint_seconds: list[int]


def canonical(value: BaseModel) -> bytes:
    return json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def checkpoints(bundle: DemoBundle) -> list[Checkpoint]:
    match = bundle.live
    engine = AdvancedMetrics(match.match_id, match.home_club_id, match.away_club_id, 5400)
    engine.extend(match.frames)
    player = MatchReplay(match, now=lambda: 0)
    cuts = []
    for cut in CUTS:
        player.seek(cut)
        cuts.append(
            Checkpoint(
                at_second=cut,
                score=player.snapshot().score,
                visible_event_ids=[e.id for e in match.events if seconds(e) <= cut],
                metrics=engine.snapshot(cut),
                context=demo_context(bundle, cut),
            )
        )
    return cuts


def manifest(recording: Recording) -> Manifest:
    raw = canonical(recording)
    return Manifest(
        sha256=hashlib.sha256(raw).hexdigest(),
        canonical_bytes=len(raw),
        match_id=recording.bundle.live.match_id,
        event_count=len(recording.bundle.live.events),
        historical_fixture_ids=sorted(recording.bundle.historical_matches),
        checkpoint_seconds=[c.at_second for c in recording.checkpoints],
    )


def validate(recording: Recording) -> None:
    bundle = recording.bundle
    if bundle.scenario_version != "ashford-demo-v1":
        raise ValueError("Unsupported scenario version")
    validate_history(bundle.league)
    clubs = {c.id: c for c in bundle.league.clubs}
    for match in [bundle.live, *bundle.historical_matches.values()]:
        validate_match(match, clubs[match.home_club_id], clubs[match.away_club_id])
    fixtures = {f.id: f for f in bundle.league.fixtures}
    for fixture_id, match in bundle.historical_matches.items():
        fixture = fixtures[fixture_id]
        goals = [
            (e.player_id, e.team_id, e.minute) for e in match.events if e.type == EventType.GOAL
        ]
        if (
            match.match_id != fixture_id
            or (fixture.home_club_id, fixture.away_club_id)
            != (match.home_club_id, match.away_club_id)
            or (fixture.home_goals, fixture.away_goals) != match.score
            or sorted(goals) != sorted((s.player_id, s.club_id, s.minute) for s in fixture.scorers)
        ):
            raise ValueError("Historical artifact disagrees with its fixture ledger")
    if recording.checkpoints != checkpoints(bundle):
        raise ValueError("Recorded checkpoints disagree with event-derived metrics or context")
    before = next(c for c in recording.checkpoints if c.at_second == 3719)
    climax = next(c for c in recording.checkpoints if c.at_second == 3720)
    if before.context.climax is not None or before.context.preview is not None:
        raise ValueError("Recording reveals the climax before its cutoff")
    pattern = climax.context.climax
    if (
        pattern is None
        or bundle.climax_goal_id not in pattern.event_ids
        or pattern.elapsed_seconds != 20
        or climax.score != (1, 1)
        or climax.context.verified_consecutive_matches != 4
        or not climax.context.earlier_meeting_fixture_ids
        or len(bundle.historical_matches) != 4
    ):
        raise ValueError("Recording does not preserve the authored climax and history")
    goal = next(e for e in bundle.live.events if e.id == bundle.climax_goal_id)
    scorer = next(p for c in bundle.league.clubs for p in c.squad if p.id == goal.player_id)
    if goal.type != EventType.GOAL or seconds(goal) != 3720 or scorer.name != "Finn Hartley":
        raise ValueError("Recording does not preserve Hartley's goal at 62:00")
    for cut in recording.checkpoints:
        visible = set(cut.visible_event_ids)
        evidence = [m.evidence for team in cut.metrics.teams for m in team.values]
        evidence += [p.evidence for p in cut.metrics.player_ratings]
        if any(set(item.event_ids) - visible for item in evidence):
            raise ValueError("Metric evidence refers to unavailable or future events")


def record(destination: Path) -> Manifest:
    bundle = build_demo()
    recording = Recording(bundle=bundle, checkpoints=checkpoints(bundle))
    validate(recording)
    info = manifest(recording)
    compressed = bytearray(gzip.compress(canonical(recording), mtime=0))
    compressed[9] = 255  # Portable gzip OS header; no filename or creation time.
    destination.mkdir(parents=True, exist_ok=False)
    (destination / PAYLOAD).write_bytes(compressed)
    (destination / "manifest.json").write_bytes(canonical(info) + b"\n")
    return info


def load(directory: Path, *, regenerate: bool = False) -> Recording:
    info = Manifest.model_validate_json((directory / "manifest.json").read_bytes())
    with gzip.open(directory / PAYLOAD, "rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Recording exceeds the supported uncompressed size")
    if len(raw) != info.canonical_bytes or hashlib.sha256(raw).hexdigest() != info.sha256:
        raise ValueError("Recording integrity check failed")
    recording = Recording.model_validate_json(raw)
    if manifest(recording) != info:
        raise ValueError("Manifest disagrees with the recorded payload")
    validate(recording)
    if regenerate and recording.bundle != build_demo():
        raise ValueError("Recording differs from the current scenario generator")
    return recording


def replay_updates(recording: Recording, start: int = 3660, end: int = 3780):
    """Virtual-clock trace with the real delivery cursor and inclusive integer cuts.

    Events before start belong to checkpoint pre-roll, not stream delivery.
    """
    if type(start) is not int or type(end) is not int or not 0 <= start <= end <= 5400:
        raise ValueError("Replay range must be integer seconds inside 0..5400")
    clock = [0.0]
    player = MatchReplay(recording.bundle.live, now=lambda: clock[0])
    player.seek(start)
    player.play()
    for elapsed in range(end - start + 1):
        clock[0] = float(elapsed)
        yield player.poll()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("record", help="Create a new recording directory")
    create.add_argument("directory", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--regenerate", action="store_true")
    replay = commands.add_parser("replay", help="Write deterministic replay updates as NDJSON")
    replay.add_argument("directory", type=Path)
    replay.add_argument("--start", type=int, default=3660)
    replay.add_argument("--end", type=int, default=3780)
    extract = commands.add_parser("extract", help="Export live MatchResult for real-time replay")
    extract.add_argument("directory", type=Path)
    extract.add_argument("--output", type=Path, required=True, help="Must be a new file")
    args = parser.parse_args()
    try:
        if args.command == "record":
            print(record(args.directory).model_dump_json(indent=2))
            return
        recording = load(args.directory, regenerate=getattr(args, "regenerate", False))
        if args.command == "verify":
            print(
                json.dumps(
                    {
                        "verified": True,
                        "manifest": manifest(recording).model_dump(),
                        "cuts": [
                            {
                                "second": c.at_second,
                                "score": c.score,
                                "events": len(c.visible_event_ids),
                                "climax": c.context.climax is not None,
                                "verified_streak": c.context.verified_consecutive_matches,
                            }
                            for c in recording.checkpoints
                        ],
                    },
                    indent=2,
                )
            )
        elif args.command == "extract":
            with args.output.open("x", encoding="utf-8") as target:
                target.write(recording.bundle.live.model_dump_json() + "\n")
        else:
            for update in replay_updates(recording, args.start, args.end):
                print(update.model_dump_json())
    except (OSError, ValueError, KeyError, StopIteration, EOFError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
