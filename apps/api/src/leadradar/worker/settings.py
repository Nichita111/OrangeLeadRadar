"""Configuration of the worker process: [worker Runtime](/architecture/services/worker.md#runtime).

All keys the job loop and the SCORE step read.
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """The worker process's configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    log_level: str = "INFO"
    database_url: SecretStr = SecretStr("")

    # Job-queue tuning ([Job queue](/architecture/services/worker.md#job-queue))
    worker_concurrency: int = 4
    job_max_attempts: int = 3
    job_retry_backoff_s: int = 30
    job_lock_timeout_s: int = 900

    # Alert window ([Alerts](/architecture/rules.md#alerts))
    alert_max_age_days: int = 14
