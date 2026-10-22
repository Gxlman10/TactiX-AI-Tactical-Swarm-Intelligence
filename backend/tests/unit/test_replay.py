"""Replay clock continuity, stable event delivery and interruptible scheduling."""

import asyncio
import json
import subprocess
import sys

import pytest

from tactix.domain.common import Point
from tactix.domain.enums import EventType, PossessionPhase, ShotOutcome
from tactix.domain.events import Event, Possession
from tactix.simulation.engine import MatchConfig, MatchResult, PossessionFrame, simulate_match
from tactix.simulation.replay import MatchReplay
from tactix.universe.generator import generate_league


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


@pytest.fixture
def match():
    def event(key, at, team, kind, **kwargs):
        return Event(
            id=key,
            match_id="m",
            minute=at // 60,
            second=at % 60,
            team_id=team,
            player_id=f"{team}1",
            type=kind,
            start=Point(x=50, y=50),
            **kwargs,
        )

    frames = []
    for key, owner, start, end, events in [
        (
            "p1",
            "a",
            0,
            20,
            [
                event("kick", 0, "a", EventType.KICKOFF),
                event(
                    "shot",
                    10,
                    "a",
                    EventType.SHOT,
                    shot_outcome=ShotOutcome.GOAL,
                    expected_value=0.2,
                ),
                event("goal", 10, "a", EventType.GOAL, subtype="from_shot:shot"),
            ],
        ),
        (
            "p2",
            "b",
            60,
            100,
            [
                event("restart", 60, "b", EventType.KICKOFF),
                event("pass", 80, "b", EventType.PASS, related_player_id="b2"),
            ],
        ),
    ]:
        for e in events:
            e.possession_id = key
        frames.append(
            PossessionFrame(
                possession=Possession(
                    id=key,
                    match_id="m",
                    team_id=owner,
                    start_minute=start // 60,
                    start_second=start % 60,
                    end_minute=end // 60,
                    end_second=end % 60,
                    phase=PossessionPhase.OUTCOME,
                    event_ids=[e.id for e in events],
                ),
                phases=[PossessionPhase.BUILD_UP, PossessionPhase.OUTCOME],
                events=events,
            )
        )
    return MatchResult(
        match_id="m",
        home_club_id="a",
        away_club_id="b",
        config=MatchConfig(duration_minutes=2),
        frames=frames,
    )


def ids(update):
    return [item.event.id for item in update.events]


def test_initial_pause_kickoff_once_and_observation_does_not_consume(match):
    clock = Clock()
    player = MatchReplay(match, now=clock)
    assert player.snapshot().status == "paused"
    clock.advance(300)
    assert player.snapshot().position_seconds == 0
    assert player.snapshot().next_sequence == 1
    assert ids(player.poll()) == ["kick"]
    assert ids(player.poll()) == []


def test_pause_resume_and_speed_change_preserve_clock_continuity(match):
    clock = Clock()
    player = MatchReplay(match, now=clock, speed=2)
    player.play()
    clock.advance(2)
    assert player.snapshot().position_seconds == 4
    player.set_speed(3)
    assert player.snapshot().position_seconds == 4
    clock.advance(2)
    player.pause()
    assert player.snapshot().position_seconds == 10
    clock.advance(100)
    assert player.snapshot().position_seconds == 10
    player.play()
    player.play()
    clock.advance(1)
    assert player.snapshot().position_seconds == 13


def test_equal_timestamps_inclusive_order_score_and_no_future_leaks(match):
    clock = Clock()
    player = MatchReplay(match, now=clock)
    player.play()
    clock.advance(9)
    assert ids(player.poll()) == ["kick"]
    assert player.snapshot().score == (0, 0)
    clock.advance(1)
    update = player.poll()
    assert ids(update) == ["shot", "goal"]
    assert [e.sequence for e in update.events] == [2, 3]
    assert update.score == (1, 0)
    assert update.next_sequence == 4
    assert player.poll().events == []


def test_finish_at_duration_not_last_event_and_play_cannot_restart(match):
    clock = Clock()
    player = MatchReplay(match, now=clock)
    player.play()
    clock.advance(81)
    assert len(player.poll().events) == 5
    assert player.snapshot().status == "playing"
    clock.advance(1000)
    update = player.poll()
    assert update.status == "finished" and update.position_seconds == 120
    player.play()
    assert player.poll().status == "finished"
    assert player.poll().events == []


def test_seek_pauses_resets_cursor_inclusively_and_reconstructs_score(match):
    player = MatchReplay(match)
    player.play()
    player.seek(10)
    update = player.poll()
    assert update.revision == 1 and update.status == "paused"
    assert ids(update) == ["shot", "goal"] and update.score == (1, 0)
    player.seek(9.5)
    assert player.snapshot().score == (0, 0)
    assert player.poll().events == []
    player.seek(11)
    assert player.snapshot().score == (1, 0)
    assert player.poll().events == []
    player.seek(0)
    assert ids(player.poll()) == ["kick"]
    assert player.snapshot().revision == 4
    player.seek(120)
    assert player.poll().status == "finished"
    player.seek(0)
    assert player.snapshot().status == "paused"


def test_inputs_and_outputs_are_isolated(match):
    player = MatchReplay(match)
    match.frames[0].events[0].id = "changed"
    update = player.poll()
    assert ids(update) == ["kick"]
    update.events[0].event.id = "mutated"
    player.seek(0)
    assert ids(player.poll()) == ["kick"]


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True, "2"])
def test_invalid_speed_rejected_without_changing_clock(match, bad):
    with pytest.raises(ValueError):
        MatchReplay(match, speed=bad)
    player = MatchReplay(match)
    before = player.snapshot()
    with pytest.raises(ValueError):
        player.set_speed(bad)
    assert player.snapshot() == before


@pytest.mark.parametrize("bad", [-1, 121, float("nan"), float("inf"), True, "10"])
def test_invalid_seek_atomic(match, bad):
    player = MatchReplay(match)
    before = player.snapshot()
    with pytest.raises(ValueError):
        player.seek(bad)
    assert player.snapshot() == before


def test_invalid_artifacts_rejected(match):
    broken = match.model_copy(deep=True)
    broken.frames[0].events[1].id = "kick"
    with pytest.raises(ValueError, match="unique"):
        MatchReplay(broken)
    broken = match.model_copy(update={"frames": []})
    with pytest.raises(ValueError, match="nonempty"):
        MatchReplay(broken)


async def test_async_complete_delivery_and_heartbeat_end(match):
    player = MatchReplay(match, speed=10000)
    player.play()
    updates = [u async for u in player.stream(tick_seconds=0.001)]
    assert [e.event.id for u in updates for e in u.events] == [e.id for e in match.events]
    assert [e.sequence for u in updates for e in u.events] == list(range(1, 6))
    assert updates[-1].status == "finished"
    assert updates[-1].position_seconds == 120


async def test_paused_stream_control_wakeup_single_consumer_and_close(match):
    clock = Clock()
    player = MatchReplay(match, now=clock)
    stream = player.stream(tick_seconds=60)
    first = await anext(stream)
    assert first.status == "paused"
    with pytest.raises(RuntimeError, match="owns"):
        player.poll()
    other = player.stream()
    with pytest.raises(RuntimeError, match="one"):
        await anext(other)
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    player.play()
    assert (await asyncio.wait_for(pending, 1)).status == "playing"
    clock.advance(10)
    player.pause()
    paused = await asyncio.wait_for(anext(stream), 1)
    assert paused.position_seconds == 10 and ids(paused) == ["shot", "goal"]
    player.seek(0)
    assert ids(await anext(stream)) == ["kick"]
    await stream.aclose()
    assert player.snapshot().status == "paused"
    assert player.poll().events == []


async def test_cancellation_while_waiting_releases_consumer_and_freezes_clock(match):
    clock = Clock()
    player = MatchReplay(match, now=clock)
    player.play()
    stream = player.stream(tick_seconds=60)
    await anext(stream)
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert player.snapshot().status == "paused"
    clock.advance(10)
    assert player.poll().position_seconds == 0


async def test_slow_consumer_catches_up_without_drops(match):
    clock = Clock()
    player = MatchReplay(match, now=clock)
    player.play()
    stream = player.stream(tick_seconds=0.001)
    first = await anext(stream)
    clock.advance(120)
    final = await asyncio.wait_for(anext(stream), 1)
    assert ids(first) + ids(final) == [e.id for e in match.events]
    assert final.status == "finished"
    await stream.aclose()


@pytest.mark.parametrize("bad", [0, -1, 61, float("nan"), True])
async def test_invalid_tick_interval(match, bad):
    stream = MatchReplay(match).stream(tick_seconds=bad)
    with pytest.raises(ValueError):
        await anext(stream)


def test_generated_match_replay_matches_event_stream_and_final_score():
    league = generate_league()
    match = simulate_match(league.clubs[0], league.clubs[1], MatchConfig(duration_minutes=2))
    clock = Clock()
    player = MatchReplay(match, now=clock)
    player.play()
    delivered = []
    for second in range(121):
        clock.value = 1000 + second
        update = player.poll()
        delivered.extend(e.event for e in update.events)
    assert delivered == match.events
    assert update.score == match.score and update.status == "finished"


def test_cli_jsonl_and_invalid_arguments(match, tmp_path):
    source = tmp_path / "match.json"
    source.write_text(match.model_dump_json(), encoding="utf-8")
    args = [
        sys.executable,
        "-m",
        "tactix.simulation.replay",
        "--input",
        str(source),
        "--speed",
        "10000",
        "--start-second",
        "10",
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    updates = [json.loads(line) for line in result.stdout.splitlines()]
    assert updates[-1]["status"] == "finished"
    assert updates[-1]["score"] == [1, 0]
    assert all(u["replay_version"] == "replay-v1" and u["revision"] == 1 for u in updates)
    assert [e["event"]["id"] for u in updates for e in u["events"]] == [
        "shot",
        "goal",
        "restart",
        "pass",
    ]
    bad = subprocess.run(args + ["--speed", "0"], capture_output=True, text=True, timeout=10)
    assert bad.returncode != 0 and "positive" in bad.stderr
