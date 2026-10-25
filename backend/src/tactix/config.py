"""Runtime configuration, loaded from environment variables (prefix ``TACTIX_``)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[3] / ".env", ".env"),
        env_prefix="TACTIX_",
        extra="ignore",
    )

    app_name: str = "TactiX"
    environment: str = "local"
    # Comma-separated browser origins; `*` keeps local development frictionless.
    cors_origins: str = "*"

    # Persistence
    database_url: str = "postgresql+psycopg://tactix:tactix@localhost:5432/tactix"

    # Model provider. The swarm runs against a provider-neutral chat-client contract
    # (Microsoft Agent Framework); this selects which adapter builds that client. "foundry"
    # is the adapter wired today — another (OpenAI, Anthropic, local) registers under its own
    # name in tactix.agents.providers without touching the runtime.
    model_provider: str = "foundry"

    # Execution bounds for the model-backed stages. Provider-neutral: they apply to whichever
    # adapter is selected, not just Foundry.
    model_timeout_seconds: float = Field(default=30, gt=0, le=120)
    model_max_attempts: int = Field(default=2, ge=1, le=2)
    model_max_tool_calls: int = Field(default=8, ge=1, le=20)
    model_max_iterations: int = Field(default=5, ge=1, le=10)
    model_max_tokens: int = Field(default=2048, ge=256, le=8192)

    # Microsoft Foundry adapter settings (used only when model_provider == "foundry").
    # Left unset until a project and deployment are available in the account.
    foundry_endpoint: str | None = None
    foundry_model: str | None = None
    foundry_authentication: Literal["cli", "default", "managed_identity"] = "cli"

    # Product
    default_language: str = "en"

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
