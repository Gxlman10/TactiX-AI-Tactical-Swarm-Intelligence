"""The provider-neutral model contract.

The swarm runs against Microsoft Agent Framework's chat-client interface, not any one
vendor. A ``ModelProvider`` owns only what is vendor-specific: validating its own
configuration and constructing (and tearing down) a MAF chat client, with whatever
credentials and transport that vendor needs. Everything else — the ``Agent`` loop, the tool
budget, the invocation limits, output validation — is provider-neutral runtime in
``tactix.agents.runtime`` and works with whatever client the provider yields.
"""

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager

from tactix.config import Settings


class ModelProvider(ABC):
    """One model-provider adapter. Concrete adapters set ``name`` and implement both hooks."""

    #: Stable identifier matched against ``Settings.model_provider``.
    name: str

    @abstractmethod
    def validate_configuration(self, settings: Settings) -> None:
        """Raise ``ValueError`` if this provider is not configured well enough to run.

        Must not contact the network, authenticate or reveal secrets — it only checks that
        the settings this adapter needs are present and well formed.
        """

    @abstractmethod
    def client(self, settings: Settings) -> AbstractAsyncContextManager:
        """Return an async context manager that yields a configured MAF chat client.

        The context manager owns the client's credentials and transport and closes them on
        exit. Implementations validate configuration before constructing anything.
        """
