"""Configuration of the worker process: [worker Runtime](/architecture/services/worker.md#runtime).

All keys the job loop and the SCORE and SIGNAL steps read.
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

    # SIGNAL step ([worker Configuration](/architecture/services/worker.md#runtime))
    usd_eur_rate: float = 0.92
    triage_chars: int = 2000
    triage_about_min_p: float = 0.5
    triage_relevance_min_p: float = 0.3
    escalation_lower: float = 0.35
    escalation_upper: float = 0.65
    evidence_max_attempts: int = 2
    evidence_min_quote_chars: int = 20
    evidence_max_quote_chars: int = 400
    evidence_max_rationale_chars: int = 300
    llm_daily_budget_eur: float = 20.0
    fixture_mode: str = "off"
    fixture_dir: str = "./fixtures"
