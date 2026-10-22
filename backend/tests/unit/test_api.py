"""HTTP contracts, visible-time boundaries and independent SSE recovery."""

import asyncio
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from tactix.api.sessions import CreateSession
from tactix.main import app


class Clock:
    value = 1000.0

    def __call__(self):
        return self.value


@pytest.fixture
def client():
    with TestClient(app) as client:
        client.clock = Clock()
        app.state.sessions.now = client.clock
        yield client


def create(client, **kwargs):
    response = client.post("/api/v1/sessions", json={"match": {"duration_minutes": 2}, **kwargs})
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


def control(client, session_id, **kwargs):
    response = client.post(f"/api/v1/sessions/{session_id}/controls", json=kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def test_health_league_openapi_and_session_lifecycle(client):
    assert client.get("/health").json()["status"] == "ok"
    league = client.get("/api/v1/league").json()
    assert len(league["clubs"]) == 10 and len(league["clubs"][0]["squad"]) == 23
    sid = create(client)
    info = client.get(f"/api/v1/sessions/{sid}").json()
    assert info["state"]["status"] == "paused" and info["state"]["score"] == [0, 0]
    assert "frames" not in info and info["state"]["events"] == []
    assert client.get("/api/v1/sessions").json()[0]["session_id"] == sid
    assert client.delete(f"/api/v1/sessions/{sid}").status_code == 204
    assert client.get(f"/api/v1/sessions/{sid}").status_code == 404
    schema = client.get("/openapi.json").json()
    assert (
        "text/event-stream"
        in schema["paths"]["/api/v1/sessions/{session_id}/stream"]["get"]["responses"]["200"][
            "content"
        ]
    )


@pytest.mark.parametrize(
    "body,code",
    [
        ({"home": "Unknown"}, 404),
        ({"away": "Ashford"}, 422),
        ({"speed": 0}, 422),
        ({"speed": True}, 422),
        ({"speed": "60"}, 422),
        ({"speed": 10001}, 422),
        ({"extra": 1}, 422),
        ({"match": {"duration_minutes": 1}}, 422),
    ],
)
def test_create_validation(client, body, code):
    assert client.post("/api/v1/sessions", json=body).status_code == code
    assert app.state.sessions.pending == 0


def test_independent_sessions_same_match_and_capacity_released(client):
    app.state.sessions.capacity = 2
    first, second = create(client), create(client)
    assert first != second
    a, b = (client.get(f"/api/v1/sessions/{sid}").json() for sid in (first, second))
    assert a["state"]["match_id"] == b["state"]["match_id"]
    control(client, first, action="play")
    assert client.get(f"/api/v1/sessions/{second}").json()["state"]["status"] == "paused"
    full = client.post("/api/v1/sessions", json={})
    assert full.status_code == 503 and full.headers["retry-after"] == "30"
    client.delete(f"/api/v1/sessions/{first}")
    assert create(client)


def test_failed_generation_releases_reservation(client, monkeypatch):
    registry = app.state.sessions

    def fail(*args):
        raise RuntimeError("generation failed")

    monkeypatch.setattr(registry, "build", fail)
    with pytest.raises(RuntimeError, match="generation failed"):
        client.post("/api/v1/sessions", json={})
    assert registry.pending == 0 and not registry.sessions


def test_controls_continuity_seek_pause_and_errors(client):
    sid = create(client)
    control(client, sid, action="play")
    client.clock.value += 1
    state = control(client, sid, action="pause")
    assert state["position_seconds"] == 60
    control(client, sid, action="speed", speed=120)
    control(client, sid, action="play")
    client.clock.value += 0.25
    assert control(client, sid, action="pause")["position_seconds"] == 90
    state = control(client, sid, action="seek", second=10)
    assert state["revision"] == 1 and state["status"] == "paused"
    for body in [
        {"action": "seek", "second": 121},
        {"action": "speed", "speed": 0},
        {"action": "play", "second": 10},
        {"action": "unknown"},
    ]:
        assert client.post(f"/api/v1/sessions/{sid}/controls", json=body).status_code == 422
    assert client.get(f"/api/v1/sessions/{sid}").json()["state"]["revision"] == 1


def test_events_pagination_and_metrics_never_expose_future(client):
    sid = create(client)
    base = f"/api/v1/sessions/{sid}"
    initial = client.get(base + "/events").json()
    assert len(initial["events"]) == 1 and initial["events"][0]["event"]["minute"] == 0
    assert client.get(base + "/metrics?at_second=1").status_code == 422
    for suffix in ["?limit=0", "?limit=501", "?after_sequence=-1"]:
        assert client.get(base + "/events" + suffix).status_code == 422
    assert client.get(base + "/events?after_sequence=100").status_code == 409
    control(client, sid, action="seek", second=90)
    assert client.get(base + "/events?revision=0").status_code == 409
    page = client.get(base + "/events?revision=1&limit=2").json()
    collected = page["events"]
    while page["has_more"]:
        page = client.get(
            base + f"/events?revision=1&limit=2&after_sequence={page['next_sequence'] - 1}"
        ).json()
        collected += page["events"]
    session = app.state.sessions.get(sid)
    expected = [e.model_dump(mode="json") for e in session.events if e.minute * 60 + e.second <= 90]
    assert [e["event"] for e in collected] == expected
    for advanced in (False, True):
        metrics = client.get(base + f"/metrics?advanced={str(advanced).lower()}").json()
        assert metrics["at_second"] == 90 and metrics["revision"] == 1
        assert metrics["metrics_version"] == ("advanced-v1" if advanced else "core-v1")
        allowed = {e["id"] for e in expected}
        assert all(
            set(v["evidence"]["event_ids"]) <= allowed
            for t in metrics["snapshot"]["teams"]
            for v in t["values"]
        )
    assert client.get(base + "/metrics?at_second=91").status_code == 422
    assert client.get(base + "/metrics?at_second=10").status_code == 200


def test_metrics_revision_change_during_compute_returns_conflict(client, monkeypatch):
    sid = create(client)
    session = app.state.sessions.get(sid)
    original = session.metrics.snapshot

    def changed(cutoff):
        snapshot = original(cutoff)
        session.seek(0)
        return snapshot

    monkeypatch.setattr(session.metrics, "snapshot", changed)
    assert client.get(f"/api/v1/sessions/{sid}/metrics?advanced=true").status_code == 409


def test_sse_headers_full_recovery_and_no_duplicate_reconnect(client):
    sid = create(client)
    session = app.state.sessions.get(sid)
    control(client, sid, action="play")
    client.clock.value += 2
    url = f"/api/v1/sessions/{sid}/stream"
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    lines = response.text.splitlines()
    packet = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
    token = next(line[4:] for line in lines if line.startswith("id: "))
    assert packet["status"] == "finished"
    assert [e["event"]["id"] for e in packet["events"]] == [e.id for e in session.events]
    assert session.subscribers == 0
    resumed = client.get(url, headers={"Last-Event-ID": token})
    final = json.loads(
        next(line[6:] for line in resumed.text.splitlines() if line.startswith("data: "))
    )
    assert final["events"] == []
    middle = len(session.events) // 2
    recovered = client.get(url, headers={"Last-Event-ID": f"{sid}:0:{middle}"})
    packet = json.loads(
        next(line[6:] for line in recovered.text.splitlines() if line.startswith("data: "))
    )
    assert [e["event"]["id"] for e in packet["events"]] == [e.id for e in session.events[middle:]]


def test_sse_rejects_stale_future_foreign_and_excess_subscribers(client):
    sid = create(client)
    url = f"/api/v1/sessions/{sid}/stream"
    for token, code in [
        ("invalid", 400),
        ("other:0:0", 400),
        (f"{sid}:0:100", 409),
        (f"{sid}:1:0", 409),
    ]:
        assert client.get(url, headers={"Last-Event-ID": token}).status_code == code
    session = app.state.sessions.get(sid)
    session.subscribers = 8
    assert client.get(url).status_code == 429
    session.subscribers = 0
    control(client, sid, action="seek", second=120)
    assert client.get(url, headers={"Last-Event-ID": f"{sid}:0:0"}).status_code == 409


async def test_two_readers_reset_delete_and_disconnect_are_independent(client):
    registry = app.state.sessions
    home, away = registry.club("Ashford"), registry.club("Northbridge")
    session = registry.build(home, away, CreateSession(match={"duration_minutes": 2}))
    releases = []
    first = session.feed(0, 0, release=lambda: releases.append("first"))
    second = session.feed(0, 0, release=lambda: releases.append("second"))
    assert (await anext(first))["data"] == (await anext(second))["data"]
    await first.aclose()
    assert releases == ["first"] and session.player.snapshot().status == "paused"
    session.player.play()
    assert session.player.snapshot().status == "playing"
    session.seek(60)
    reset = await asyncio.wait_for(anext(second), 1)
    assert reset["event"] == "reset" and json.loads(reset["data"])["revision"] == 1
    session.close()
    closed = await anext(second)
    assert closed["event"] == "closed"
    await second.aclose()
    assert releases == ["first", "second"]


def test_pending_capacity_and_resume_minimum_after_seek(client):
    registry = app.state.sessions
    registry.capacity = 1
    registry.reserve()
    with pytest.raises(HTTPException) as full:
        registry.reserve()
    assert full.value.status_code == 503
    registry.pending -= 1
    sid = create(client)
    session = registry.get(sid)
    session.seek(80)
    with pytest.raises(HTTPException) as stale:
        session.resume_cursor(f"{sid}:1:0")
    assert stale.value.status_code == 409


def test_shutdown_closes_and_clears_sessions(client):
    sid = create(client)
    registry = app.state.sessions
    session = registry.get(sid)
    registry.close()
    assert session.closed and not registry.sessions
