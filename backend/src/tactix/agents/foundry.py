"""Real MAF/Foundry adapter and bounded execution of the two evidence specialists."""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

from tactix.agents.boundaries import build_request, validate_output
from tactix.agents.contracts import SPECS, FindingsOutput
from tactix.agents.tools import TOOL_ARGUMENTS, EvidenceTools
from tactix.config import Settings
from tactix.domain.agents import MatchContext
from tactix.domain.enums import AgentName

RUNTIME_VERSION = "specialists-maf-v1"
SPECIALISTS = (AgentName.TACTICAL_ANALYST, AgentName.HISTORIAN)


class ToolTrace(BaseModel):
    name: str
    status: Literal["ok", "rejected", "budget_exceeded"]


class AgentExecution(BaseModel):
    agent: AgentName
    status: Literal["complete", "degraded"]
    attempts: int
    elapsed_ms: int
    tool_calls: list[ToolTrace]
    failure: (
        Literal["timeout", "invalid_output", "provider_error", "tool_budget", "duplicate_ids"]
        | None
    )


class SpecialistRun(BaseModel):
    runtime_version: str = RUNTIME_VERSION
    match_id: str
    at_second: int
    revision: int
    context: MatchContext
    executions: list[AgentExecution]
    partial: bool


def require_foundry_configuration(settings: Settings) -> None:
    if (
        not settings.foundry_endpoint
        or not settings.foundry_model
        or not settings.foundry_model.strip()
    ):
        raise ValueError("Configure TACTIX_FOUNDRY_ENDPOINT and TACTIX_FOUNDRY_MODEL")
    endpoint = urlsplit(settings.foundry_endpoint)
    if (
        endpoint.scheme != "https"
        or not endpoint.hostname
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
        or "/api/projects/" not in endpoint.path
        or not endpoint.path.split("/api/projects/", 1)[1].strip("/")
    ):
        raise ValueError("TACTIX_FOUNDRY_ENDPOINT must be an HTTPS Foundry project endpoint")


def invocation_limits(settings: Settings) -> dict:
    return {
        "max_iterations": settings.foundry_max_iterations,
        "max_function_calls": settings.foundry_max_tool_calls,
        "max_duration_seconds": settings.foundry_timeout_seconds,
        "allow_concurrent_invocation": False,
        "terminate_on_unknown_calls": True,
        "include_detailed_errors": False,
    }


@asynccontextmanager
async def foundry_client(settings: Settings):
    """Own and close credentials, project pipeline and inference transport on one loop."""
    require_foundry_configuration(settings)
    from agent_framework.foundry import FoundryChatClient
    from azure.ai.projects.aio import AIProjectClient
    from azure.identity.aio import (
        AzureCliCredential,
        DefaultAzureCredential,
        ManagedIdentityCredential,
    )

    credential = {
        "cli": AzureCliCredential,
        "default": DefaultAzureCredential,
        "managed_identity": ManagedIdentityCredential,
    }[settings.foundry_authentication]()
    async with (
        credential,
        AIProjectClient(
            endpoint=settings.foundry_endpoint, credential=credential, retry_total=0
        ) as project,
    ):
        client = FoundryChatClient(
            project_client=project,
            model=settings.foundry_model,
            function_invocation_configuration=invocation_limits(settings),
        )
        # Disable hidden transport retries: the application owns the bounded attempt budget.
        client.client.max_retries = 0
        client.client.timeout = settings.foundry_timeout_seconds
        try:
            yield client
        finally:
            await client.client.close()


class ToolBudget:
    def __init__(self, maximum: int):
        self.maximum = maximum
        self.traces: list[ToolTrace] = []
        self.exhausted = False

    def bind(self, role: AgentName, scope: EvidenceTools):
        from agent_framework import FunctionTool

        def handler(name):
            async def invoke(**arguments):
                if len(self.traces) >= self.maximum:
                    self.exhausted = True
                    # Keep the diagnostic artifact bounded too.
                    if not any(t.status == "budget_exceeded" for t in self.traces):
                        self.traces.append(ToolTrace(name=name, status="budget_exceeded"))
                    return json.dumps({"error": "tool_budget_exceeded"})
                try:
                    result = scope.invoke(role, name, arguments)
                except (ValueError, PermissionError):
                    self.traces.append(ToolTrace(name=name, status="rejected"))
                    return json.dumps({"error": "invalid_tool_request"})
                self.traces.append(ToolTrace(name=name, status="ok"))
                return json.dumps(result, ensure_ascii=False, allow_nan=False)

            return invoke

        return [
            FunctionTool(
                name=name,
                description=TOOL_ARGUMENTS[name][1],
                input_model=TOOL_ARGUMENTS[name][0],
                func=handler(name),
            )
            for name in SPECS[role].tools
        ]


async def _specialist(role, client, scope, settings):
    from agent_framework import Agent

    state = MatchContext(
        match_id=scope.match_id, minute=scope.at_second // 60, metrics=scope.metrics()
    )
    request = build_request(role, state, scope)
    budget = ToolBudget(settings.foundry_max_tool_calls)
    began, attempts, failure = time.monotonic(), 0, None
    findings = []
    try:
        async with asyncio.timeout(settings.foundry_timeout_seconds):
            for attempts in range(1, settings.foundry_max_attempts + 1):
                agent = Agent(
                    client=client,
                    name=role.value,
                    instructions=request["messages"][0]["content"],
                    tools=budget.bind(role, scope),
                )
                message = request["messages"][1]["content"]
                if attempts > 1:
                    message += (
                        "\nThe previous response failed validation. Return only the required JSON; "
                        "use existing IDs and role-correct findings."
                    )
                try:
                    response = await agent.run(
                        message,
                        options={
                            "response_format": FindingsOutput,
                            "max_tokens": settings.foundry_max_tokens,
                            "store": False,
                        },
                    )
                    if budget.exhausted:
                        failure = "tool_budget"
                        break
                    parsed = validate_output(role, response.text, state, scope)
                except ValueError:
                    failure = "invalid_output"
                    continue
                except Exception:
                    # Provider exception messages can contain endpoints, payloads or credentials.
                    failure = "provider_error"
                    break
                findings, failure = parsed.findings, None
                break
    except TimeoutError:
        failure = "timeout"
    except Exception:
        failure = "provider_error"
    if failure is not None:
        findings = []
    execution = AgentExecution(
        agent=role,
        status="degraded" if failure else "complete",
        attempts=attempts,
        elapsed_ms=round((time.monotonic() - began) * 1000),
        tool_calls=budget.traces,
        failure=failure,
    )
    return findings, execution


async def run_specialists(
    scope: EvidenceTools, settings: Settings, *, client=None
) -> SpecialistRun:
    """Parallel fan-out with fresh Agent instances and a deterministic merge order.

    Injected clients are for offline SDK tests. The normal path constructs the real
    Foundry provider; it never substitutes a fabricated response on provider failure.
    """
    if client is None:
        async with foundry_client(settings) as provider:
            return await run_specialists(scope, settings, client=provider)
    client.function_invocation_configuration.update(invocation_limits(settings))
    pairs = await asyncio.gather(
        *(_specialist(role, client, scope, settings) for role in SPECIALISTS)
    )
    context = MatchContext(
        match_id=scope.match_id, minute=scope.at_second // 60, metrics=scope.metrics()
    )
    seen, executions = set(), []
    for role, (findings, execution) in zip(SPECIALISTS, pairs, strict=True):
        if any(f.id in seen for f in findings):
            findings = []
            execution.status, execution.failure = "degraded", "duplicate_ids"
        if execution.status == "degraded":
            context.degraded.append(role)
        else:
            seen.update(f.id for f in findings)
        if role == AgentName.TACTICAL_ANALYST:
            context.analyst_findings = findings
        else:
            context.historian_findings = findings
        executions.append(execution)
    return SpecialistRun(
        match_id=scope.match_id,
        at_second=scope.at_second,
        revision=scope.revision,
        context=context,
        executions=executions,
        partial=bool(context.degraded),
    )
