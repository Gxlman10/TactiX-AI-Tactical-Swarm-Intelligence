"""Real HTTP/SSE sockets: simultaneous readers and reconnect after disconnect."""

import asyncio
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from tactix.main import app


async def packets(response):
    fields = {}
    async for line in response.aiter_lines():
        if not line:
            if "data" in fields:
                yield fields
            fields = {}
        elif ": " in line:
            name, value = line.split(": ", 1)
            fields[name] = value


@pytest.mark.integration
async def test_socket_broadcast_and_last_event_id_recovery():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    config = uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=2)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline, "Server startup failed"
            await asyncio.sleep(0.01)
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            created = await client.post(
                "/api/v1/sessions", json={"match": {"duration_minutes": 2}, "speed": 1000}
            )
            assert created.status_code == 201
            sid = created.json()["session_id"]
            stream_url = f"/api/v1/sessions/{sid}/stream"
            ready = [asyncio.Event(), asyncio.Event()]

            async def consume(index, disconnect_early=False, token=None):
                delivered, last = [], None
                headers = {"Last-Event-ID": token} if token else {}
                async with client.stream("GET", stream_url, headers=headers) as response:
                    assert response.status_code == 200
                    async for packet in packets(response):
                        state = json.loads(packet["data"])
                        delivered.extend(e["sequence"] for e in state["events"])
                        last = packet["id"]
                        ready[index].set()
                        if state["status"] == "finished" or (
                            disconnect_early and len(delivered) > 1
                        ):
                            break
                return delivered, last

            first = asyncio.create_task(consume(0, disconnect_early=True))
            second = asyncio.create_task(consume(1))
            await asyncio.wait_for(asyncio.gather(*(r.wait() for r in ready)), 3)
            playing = await client.post(f"/api/v1/sessions/{sid}/controls", json={"action": "play"})
            assert playing.status_code == 200
            (partial, token), (complete, _) = await asyncio.wait_for(
                asyncio.gather(first, second), 5
            )
            recovered, _ = await consume(0, token=token)
            visible = (await client.get(f"/api/v1/sessions/{sid}/events?limit=500")).json()
            expected = [e["sequence"] for e in visible["events"]]
            assert not visible["has_more"]
            assert partial + recovered == complete == expected
            assert expected == list(range(1, len(expected) + 1))
            assert (await client.get(f"/api/v1/sessions/{sid}")).json()["state"][
                "status"
            ] == "finished"
            deleted = await client.delete(f"/api/v1/sessions/{sid}")
            assert deleted.status_code == 204
    finally:
        server.should_exit = True
        await asyncio.to_thread(thread.join, 5)
        listener.close()
        assert not thread.is_alive(), "Test server did not stop"
