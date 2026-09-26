"""Configuration of the worker process: [worker Runtime](/architecture/services/worker.md#runtime).
Only the keys the worker's code reads today are here, with `DATABASE_URL` of the
[api Runtime](/architecture/services/api.md#runtime) that the job loop reads."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from leadradar.settings import FixtureMode


class WorkerSettings(BaseSettings):
    """The worker process's configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    log_level: str = "INFO"

    database_url: SecretStr
    fixture_mode: FixtureMode = "off"
    clock_file: Path | None = None
    worker_concurrency: int = 4
    job_max_attempts: int = 3
    job_retry_backoff_s: int = 30
    job_lock_timeout_s: int = 900
    job_poll_interval_s: int = 1
    refresh_interval_hours: int = 24
