"""Configuration of the worker process: [worker Runtime](/architecture/services/worker.md#runtime).
Only the keys the worker's code reads today are here; `DATABASE_URL` is added with the job loop
that first reads it ([S-PIP-01])."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """The worker process's configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
