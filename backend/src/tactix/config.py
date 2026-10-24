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

    # Microsoft Foundry (models). Left unset until availability is verified in the account.
    foundry_endpoint: str | None = None
    foundry_api_key: str | None = None
    foundry_model: str | None = None
    foundry_authentication: Literal["cli", "default", "managed_identity"] = "cli"
    foundry_timeout_seconds: float = Field(default=30, gt=0, le=120)
    foundry_max_attempts: int = Field(default=2, ge=1, le=2)
    foundry_max_tool_calls: int = Field(default=8, ge=1, le=20)
    foundry_max_iterations: int = Field(default=5, ge=1, le=10)
    foundry_max_tokens: int = Field(default=2048, ge=256, le=8192)

    # Product
    default_language: str = "en"

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
