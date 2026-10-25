"""Microsoft Foundry adapter: validate the project endpoint and build a MAF chat client.

This is the one place that knows anything Azure/Foundry-specific — the project endpoint
shape, Entra credentials and the MAF ``FoundryChatClient`` transport. The optional SDK is
imported lazily inside ``client`` so the base backend (and configuration validation) import
without the ``agents`` extra installed.
"""

from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from tactix.agents.providers.base import ModelProvider
from tactix.agents.runtime import invocation_limits
from tactix.config import Settings


class FoundryProvider(ModelProvider):
    name = "foundry"

    def validate_configuration(self, settings: Settings) -> None:
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

    @asynccontextmanager
    async def client(self, settings: Settings):
        """Own and close credentials, project pipeline and inference transport on one loop."""
        self.validate_configuration(settings)
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
            client.client.timeout = settings.model_timeout_seconds
            try:
                yield client
            finally:
                await client.client.close()
