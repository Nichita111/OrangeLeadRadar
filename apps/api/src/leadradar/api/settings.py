"""Configuration of the api process: [api Runtime](/architecture/services/api.md#runtime)
and the [worker Runtime](/architecture/services/worker.md#runtime) keys the api's health
checks read. Read once at start and passed in; no other module reads the environment."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

FixtureMode = Literal["off", "record", "replay"]


class ApiSettings(BaseSettings):
    """The api process's configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr
    log_level: str = "INFO"
    health_timeout_ms: int = 2000

    embedder_url: str = "http://embedder:80"
    embedding_dim: int = 1024

    fixture_mode: FixtureMode = "off"
    fixture_dir: Path = Path("./fixtures")

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
