"""Model-provider adapters behind the neutral contract.

Foundry is the adapter wired today. To add another (OpenAI, Anthropic, a local model),
implement ``ModelProvider`` and register an instance in ``PROVIDERS`` under its ``name`` —
no change to the runtime or the call sites is needed, because they resolve the provider
through ``get_provider`` and drive whatever MAF client it yields.
"""

from tactix.agents.providers.base import ModelProvider
from tactix.agents.providers.foundry import FoundryProvider
from tactix.config import Settings

PROVIDERS: dict[str, ModelProvider] = {FoundryProvider.name: FoundryProvider()}


def get_provider(settings: Settings) -> ModelProvider:
    """Return the configured provider adapter, or raise ``ValueError`` for an unknown name."""
    try:
        return PROVIDERS[settings.model_provider]
    except KeyError:
        raise ValueError(
            f"Unknown TACTIX_MODEL_PROVIDER {settings.model_provider!r}; "
            f"available: {', '.join(sorted(PROVIDERS))}"
        ) from None


__all__ = ["ModelProvider", "FoundryProvider", "PROVIDERS", "get_provider"]
