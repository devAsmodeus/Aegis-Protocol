"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for Aegis Protocol services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="aegis-protocol")
    app_env: Literal["development", "staging", "production"] = Field(default="development")
    app_version: str = Field(default="0.1.0")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    database_url: str | None = Field(default=None)
    redis_url: str | None = Field(default=None)
    qdrant_url: str | None = Field(default=None)
    qdrant_api_key: str | None = Field(default=None)

    zerog_rpc_url: str | None = Field(default=None)
    zerog_storage_endpoint: str | None = Field(default=None)
    zerog_compute_endpoint: str | None = Field(default=None)
    zerog_da_endpoint: str | None = Field(default=None)
    zerog_api_key: str | None = Field(default=None)
    zerog_private_key: str | None = Field(default=None)

    ens_parent_domain: str | None = Field(default=None)
    eth_rpc_url: str | None = Field(default=None)

    telegram_bot_token: str | None = Field(default=None)
    discord_bot_token: str | None = Field(default=None)

    sentry_dsn: str | None = Field(default=None)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    return Settings()
