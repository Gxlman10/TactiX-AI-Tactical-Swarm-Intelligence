"""Real MAF Agent/FunctionTool loop with a controlled model, never cloud inference."""

import asyncio
import json
import subprocess
import sys
from collections import Counter

import pytest

pytest.importorskip("agent_framework")
from agent_framework import BaseChatClient, ChatResponse, Content, FunctionInvocationLayer, Message

from tactix.agents.foundry import (
    ToolBudget,
    foundry_client,
    require_foundry_configuration,
    run_specialists,
)
from tactix.agents.tools import EvidenceTools
from tactix.config import Settings
from tactix.demo.scenario import build_demo
from tactix.domain.enums import AgentName

A, H = AgentName.TACTICAL_ANALYST, AgentName.HISTORIAN


@pytest.fixture(scope="module")
def scope():
    demo = build_demo()
    return EvidenceTools(
        demo.live, demo.league, 3720, revision=7, historical_matches=demo.historical_matches
    )


class ScriptedModel(FunctionInvocationLayer, BaseChatClient):
    """Only the model response is controlled; MAF executes real local function tools."""

    def __init__(self, scope, modes=None):
        super().__init__()
        self.scope, self.modes = scope, modes or {}
        self.counts = Counter()
        self.tool_results = []
        self.active = self.peak = 0

    async def _inner_get_response(self, *, messages, stream, options, **kwargs):
        await self._validate_options(options)
        assert not stream
        system = str(options.get("instructions", "")) + "\n".join(m.text for m in messages)
        role = A if "# Tactical Analyst" in system else H
        self.counts[role] += 1
        count, mode = self.counts[role], self.modes.get(role, "ok")
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.005)
            if mode == "hang":
                await asyncio.Event().wait()
            if mode == "provider_error":
                raise RuntimeError("private-provider-error-and-test-secret")
            for message in messages:
                for content in message.contents:
                    if content.type == "function_result":
                        self.tool_results.append(content)
            if count == 1:
                calls = 3 if mode == "budget" else 1
                return ChatResponse(
                    messages=[
                        Message(
                            "assistant",
                            [
                                Content.from_function_call(
                                    f"{role}-{i}", "read_metrics", arguments={}
                                )
                                for i in range(calls)
                            ],
                        )
                    ]
                )
            if mode == "invalid" or mode == "retry" and count == 2:
                return ChatResponse(messages=[Message("assistant", ["not JSON"])])
            ids = [key for key in self.scope.live_events][-1:]
            data = {
                "findings": [
                    {
                        "id": "collision" if mode == "duplicate" else f"{role}-62",
                        "agent": role.value,
                        "moment_minute": 62,
                        "frame": "tactical" if role == A else "historical",
                        "claim": "The visible evidence includes the current goal.",
                        "confidence": 0.8,
                        "evidence": {"event_ids": ids, "description": "Observed live goal."},
                        "references": [],
                    }
                ]
            }
            if mode == "invalid_id":
                data["findings"][0]["evidence"]["event_ids"] = ["invented"]
            return ChatResponse(messages=[Message("assistant", [json.dumps(data)])])
        finally:
            self.active -= 1


def options(**kwargs):
    return Settings(_env_file=None, foundry_timeout_seconds=5, **kwargs)


async def test_real_maf_agents_execute_tools_concurrently_and_validate(scope):
    client = ScriptedModel(scope)
    result = await run_specialists(scope, options(), client=client)
    assert not result.partial and result.revision == 7 and result.at_second == 3720
    assert result.context.analyst_findings[0].agent == A
    assert result.context.historian_findings[0].agent == H
    assert client.peak == 2 and len(client.tool_results) >= 2
    assert all(
        e.tool_calls[0].name == "read_metrics" and e.tool_calls[0].status == "ok"
        for e in result.executions
    )
    assert all(e.attempts == 1 for e in result.executions)


async def test_malformed_output_retry_and_budget_survive_attempts(scope):
    result = await run_specialists(scope, options(), client=ScriptedModel(scope, {A: "retry"}))
    assert not result.partial and result.executions[0].attempts == 2
    assert len(result.executions[0].tool_calls) == 1


@pytest.mark.parametrize(
    "mode,code",
    [
        ("invalid", "invalid_output"),
        ("invalid_id", "invalid_output"),
        ("provider_error", "provider_error"),
    ],
)
async def test_one_failure_does_not_fabricate_or_drop_other_specialist(scope, mode, code):
    result = await run_specialists(scope, options(), client=ScriptedModel(scope, {A: mode}))
    assert result.partial and result.context.degraded == [A]
    assert result.context.analyst_findings == [] and result.context.historian_findings
    assert result.executions[0].failure == code
    assert "private-provider-error" not in result.model_dump_json()


async def test_timeout_cancels_stalled_role_but_preserves_completed_role(scope):
    settings = Settings(_env_file=None, foundry_timeout_seconds=0.3)
    result = await run_specialists(scope, settings, client=ScriptedModel(scope, {A: "hang"}))
    assert result.context.degraded == [A] and result.executions[0].failure == "timeout"
    assert result.context.historian_findings


async def test_parallel_function_batch_cannot_bypass_local_budget(scope):
    result = await run_specialists(
        scope, options(foundry_max_tool_calls=1), client=ScriptedModel(scope, {A: "budget"})
    )
    assert result.partial and result.executions[0].failure == "tool_budget"
    assert len(result.executions[0].tool_calls) <= 2
    assert result.context.analyst_findings == []


async def test_cross_role_duplicate_ids_are_not_silently_renamed(scope):
    result = await run_specialists(
        scope, options(), client=ScriptedModel(scope, {A: "duplicate", H: "duplicate"})
    )
    assert result.context.analyst_findings[0].id == "collision"
    assert result.context.historian_findings == []
    assert result.context.degraded == [H] and result.executions[1].failure == "duplicate_ids"


async def test_outer_cancellation_propagates(scope):
    task = asyncio.create_task(
        run_specialists(scope, options(), client=ScriptedModel(scope, {A: "hang", H: "hang"}))
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_actual_function_tool_schemas_and_roles(scope):
    budget = ToolBudget(8)
    assert {t.name for t in budget.bind(A, scope)} == {"read_metrics", "read_events"}
    assert "player_goals" in {t.name for t in budget.bind(H, scope)}


@pytest.mark.parametrize(
    "endpoint",
    [
        None,
        "http://project/api/projects/test",
        "https://example.test",
        "https://user:secret@example.test/api/projects/test",
        "https://example.test/api/projects/test?key=secret",
    ],
)
def test_configuration_rejects_missing_or_non_project_endpoint(endpoint):
    with pytest.raises(ValueError):
        require_foundry_configuration(
            Settings(_env_file=None, foundry_endpoint=endpoint, foundry_model="deployment")
        )


def test_valid_configuration_does_not_claim_cloud_access():
    settings = Settings(
        _env_file=None,
        foundry_endpoint="https://example.test/api/projects/test",
        foundry_model="deployment",
    )
    require_foundry_configuration(settings)


async def test_real_foundry_client_construction_and_transport_cleanup_without_inference():
    from agent_framework.foundry import FoundryChatClient

    settings = Settings(
        _env_file=None,
        foundry_endpoint="https://example.test/api/projects/test",
        foundry_model="deployment",
    )
    async with foundry_client(settings) as client:
        assert isinstance(client, FoundryChatClient)
        assert client.client.max_retries == 0
        assert not client.client.is_closed()
    assert client.client.is_closed()


def test_api_analysis_missing_configuration_and_stale_revision(monkeypatch):
    from fastapi.testclient import TestClient

    from tactix.api import routes
    from tactix.main import app

    monkeypatch.setattr(routes, "settings", Settings(_env_file=None))
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions", json={"scenario": "ashford-demo-v1"}).json()[
            "session_id"
        ]
        base = f"/api/v1/sessions/{sid}"
        assert client.post(base + "/analyze").status_code == 503
        configured = Settings(
            _env_file=None,
            foundry_endpoint="https://example.test/api/projects/test",
            foundry_model="deployment",
        )
        monkeypatch.setattr(routes, "settings", configured)
        client.post(base + "/controls", json={"action": "seek", "second": 3720})

        async def controlled(scope, settings):
            return await run_specialists(scope, settings, client=ScriptedModel(scope))

        monkeypatch.setattr(routes, "run_specialists", controlled)
        response = client.post(base + "/analyze")
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == 1 and not response.json()["partial"]
        session = app.state.sessions.get(sid)
        session.analyzing = True
        assert client.post(base + "/analyze").status_code == 409
        session.analyzing = False

        async def stale(scope, settings):
            result = await controlled(scope, settings)
            session.seek(0)
            return result

        monkeypatch.setattr(routes, "run_specialists", stale)
        assert client.post(base + "/analyze").status_code == 409
        assert not session.analyzing


def test_cli_missing_configuration_fails_without_fabricated_output(tmp_path, monkeypatch):
    # Run from a directory without .env; explicitly blank config overrides any root .env.
    monkeypatch.setenv("TACTIX_FOUNDRY_ENDPOINT", "")
    monkeypatch.setenv("TACTIX_FOUNDRY_MODEL", "")
    output = tmp_path / "result.json"
    result = subprocess.run(
        [sys.executable, "-m", "tactix.agents.live", "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and not output.exists()
    assert "Check Foundry configuration" in result.stderr
