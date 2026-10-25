"""Persisted demo integrity, semantic drift, offline playback and reproducibility."""

import gzip
import json
import math
import subprocess
import sys
from pathlib import Path
from shutil import copytree

import pytest

from tactix.demo import recording as module
from tactix.demo.evidence import seconds
from tactix.demo.recording import (
    PAYLOAD,
    canonical,
    equivalent_bundles,
    load,
    manifest,
    record,
    replay_updates,
)

SOURCE = Path(__file__).resolve().parents[3] / "data/recordings/ashford-demo-v1"


@pytest.fixture(scope="module")
def recorded():
    return load(SOURCE)


def test_committed_recording_verifies_and_matches_current_generator(recorded):
    assert load(SOURCE, regenerate=True) == recorded
    assert len(recorded.bundle.live.events) == 649
    assert len(recorded.bundle.historical_matches) == 4
    assert len(recorded.checkpoints) == 9
    assert recorded.agent_inference is False


def test_load_is_independent_of_generator_and_services(monkeypatch, recorded):
    def forbidden():
        pytest.fail("Playback must not regenerate the recording")

    monkeypatch.setattr(module, "build_demo", forbidden)
    assert load(SOURCE) == recorded
    assert len(list(replay_updates(recorded))) == 121


def test_regeneration_is_byte_identical_and_cannot_overwrite(tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    assert record(first) == record(second)
    for name in (PAYLOAD, "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    rebuilt, reference = load(first), load(SOURCE)
    assert equivalent_bundles(rebuilt.bundle, reference.bundle)
    assert rebuilt.checkpoints == reference.checkpoints
    with pytest.raises(FileExistsError):
        record(first)


def test_payload_corruption_and_truncation_are_rejected(tmp_path):
    directory = copytree(SOURCE, tmp_path / "corrupt")
    payload = directory / PAYLOAD
    raw = gzip.decompress(payload.read_bytes()).replace(
        b'"authored-synthetic"', b'"changed-synthetic"'
    )
    payload.write_bytes(gzip.compress(raw, mtime=0))
    with pytest.raises(ValueError, match="integrity"):
        load(directory)
    payload.write_bytes((SOURCE / PAYLOAD).read_bytes()[:100])
    with pytest.raises((EOFError, OSError)):
        load(directory)


def test_manifest_metadata_or_version_drift_is_rejected(tmp_path):
    directory = copytree(SOURCE, tmp_path / "metadata")
    path = directory / "manifest.json"
    info = json.loads(path.read_bytes())
    info["event_count"] += 1
    path.write_text(json.dumps(info), encoding="utf-8")
    with pytest.raises(ValueError, match="Manifest disagrees"):
        load(directory)
    info["format_version"] = "tactix-recording-v99"
    path.write_text(json.dumps(info), encoding="utf-8")
    with pytest.raises(ValueError):
        load(directory)


def test_rehashed_forged_checkpoint_is_rejected(tmp_path, recorded):
    directory = copytree(SOURCE, tmp_path / "forged")
    changed = recorded.model_copy(deep=True)
    changed.checkpoints[4].context.preview = "Premature goal"
    (directory / PAYLOAD).write_bytes(gzip.compress(canonical(changed), mtime=0))
    (directory / "manifest.json").write_bytes(canonical(manifest(changed)))
    with pytest.raises(ValueError, match="checkpoints disagree"):
        load(directory)


def test_replay_has_exact_order_no_duplicates_and_inclusive_goal_boundary(recorded):
    updates = list(replay_updates(recorded))
    actual = [item.event.id for update in updates for item in update.events]
    expected = [e.id for e in recorded.bundle.live.events if 3660 <= seconds(e) <= 3780]
    assert actual == expected and len(actual) == len(set(actual))
    before, goal = updates[59], updates[60]
    assert before.position_seconds == 3719 and before.score == (1, 0)
    assert goal.position_seconds == 3720 and goal.score == (1, 1)
    assert recorded.bundle.climax_goal_id not in [e.event.id for e in before.events]
    assert recorded.bundle.climax_goal_id in [e.event.id for e in goal.events]
    assert [u.model_dump_json() for u in updates] == [
        u.model_dump_json() for u in replay_updates(recorded)
    ]
    assert all(seconds(item.event) <= u.position_seconds for u in updates for item in u.events)
    final = list(replay_updates(recorded, 0, 5400))[-1]
    assert final.status == "finished" and final.score == recorded.bundle.live.score


@pytest.mark.parametrize("start,end", [(-1, 1), (1, 5401), (5, 4), (True, 6), (1.5, 2)])
def test_invalid_replay_ranges_are_rejected(recorded, start, end):
    with pytest.raises(ValueError, match="Replay range"):
        list(replay_updates(recorded, start, end))


def test_cli_extraction_replay_and_overwrite_protection(tmp_path):
    command = [sys.executable, "-m", "tactix.demo.recording"]
    target = tmp_path / "match.json"
    extracted = subprocess.run(
        command + ["extract", str(SOURCE), "--output", str(target)], capture_output=True, text=True
    )
    assert extracted.returncode == 0, extracted.stderr
    assert json.loads(target.read_bytes())["match_id"] == manifest(load(SOURCE)).match_id
    duplicate = subprocess.run(
        command + ["extract", str(SOURCE), "--output", str(target)], capture_output=True, text=True
    )
    assert duplicate.returncode != 0
    replay = subprocess.run(
        command + ["replay", str(SOURCE), "--start", "3719", "--end", "3720"],
        capture_output=True,
        text=True,
    )
    assert replay.returncode == 0, replay.stderr
    cuts = [json.loads(line) for line in replay.stdout.splitlines()]
    assert [c["score"] for c in cuts] == [[1, 0], [1, 1]]


def test_regeneration_tolerates_only_insignificant_libm_angle_roundoff(recorded):
    original = recorded.bundle
    changed = original.model_copy(deep=True)
    event = next(e for e in changed.live.events if e.angle is not None)
    initial = event.angle
    event.angle = math.nextafter(initial, math.inf)
    assert event.angle != initial
    assert equivalent_bundles(original, changed)
    event.angle = initial + 1e-9
    assert not equivalent_bundles(original, changed)
    event.angle = initial
    event.start.x += 1e-12
    assert not equivalent_bundles(original, changed)
    changed = original.model_copy(deep=True)
    changed.live.events[0].id = "different-event"
    assert not equivalent_bundles(original, changed)
