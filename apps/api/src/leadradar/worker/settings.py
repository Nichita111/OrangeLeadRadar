"""Configuration of the worker process: [worker Runtime](/architecture/services/worker.md#runtime).
Only the keys the worker's code reads today are here."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from leadradar.logs import LogLevel


class WorkerSettings(BaseSettings):
    """The worker process's configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    log_level: LogLevel = "INFO"
