"""Configuration of the api process: [api Runtime](/architecture/services/api.md#runtime)
and the [worker Runtime](/architecture/services/worker.md#runtime) keys the api's health
checks read. Read once at start and passed in; no other module reads the environment.

Lives beside `core`, `db`, `api`, `audit` and `worker` rather than inside `api/` (a router
package) because a capability package (`audit`) also needs it: `api` importing `audit`, and
`audit` importing back from `api`, would be a layering cycle
([Coding Structure](/guidelines/coding.md#structure))."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

FixtureMode = Literal["off", "record", "replay"]


class ApiSettings(BaseSettings):
    """The api process's configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: SecretStr
    migration_database_url: SecretStr
    log_level: str = "INFO"
    health_timeout_ms: int = 2000

    embedder_url: str = "http://embedder:80"
    embedding_dim: int = 1024

    fixture_mode: FixtureMode = "off"
    fixture_dir: Path = Path("./fixtures")
    clock_file: Path | None = None

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    impact_period_days: int = 30
    manual_research_minutes_per_account: int = 120
    session_ttl_hours: int = 12
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    password_min_length: int = 12
