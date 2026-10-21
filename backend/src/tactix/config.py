"""Runtime configuration, loaded from environment variables (prefix ``TACTIX_``)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="TACTIX_", extra="ignore"
    )

    app_name: str = "TactiX"
    environment: str = "local"

    # Persistence
    database_url: str = "postgresql+psycopg://tactix:tactix@localhost:5432/tactix"

    # Microsoft Foundry (models). Left unset until availability is verified in the account.
    foundry_endpoint: str | None = None
    foundry_api_key: str | None = None
    foundry_model: str | None = None

    # Product
    default_language: str = "en"


settings = Settings()
