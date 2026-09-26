"""Configuration of the worker process: [worker Runtime](/architecture/services/worker.md#runtime).
Only the keys the worker's code reads today are here, with `DATABASE_URL` of the
[api Runtime](/architecture/services/api.md#runtime) that the job loop reads, and the keys the
SCORE and SIGNAL steps read."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from leadradar.ai.settings import AiGatewaySettings


class WorkerSettings(AiGatewaySettings):
    """The worker process's configuration; fixture mode, `CLOCK_FILE` and the AI gateway's keys
    come from `AiGatewaySettings`."""

    model_config = SettingsConfigDict(extra="ignore")

    log_level: str = "INFO"

    database_url: SecretStr
    worker_concurrency: int = 4
    job_max_attempts: int = 3
    job_retry_backoff_s: int = 30
    job_lock_timeout_s: int = 900
    job_poll_interval_s: int = 1
    refresh_interval_hours: int = 24
    scheduler_tick_s: int = 60
    scheduler_max_enqueue: int = 20

    #: [Plug-in availability](/architecture/rules.md#plug-in-availability): unset by default;
    #: a plug-in whose key is unset is unavailable. Declared here too, as `DATABASE_URL` is,
    #: for the scheduler's own enqueueing of a refresh's first jobs.
    crunchbase_api_key: SecretStr | None = None
    newsapi_key: SecretStr | None = None
    serpapi_key: SecretStr | None = None

    #: Alert window ([Alerts](/architecture/rules.md#alerts))
    alert_max_age_days: int = 14

    # SIGNAL step ([worker Configuration](/architecture/services/worker.md#runtime))
    triage_chars: int = 2000
    triage_about_min_p: float = 0.5
    triage_relevance_min_p: float = 0.3
    escalation_lower: float = 0.35
    escalation_upper: float = 0.65
    evidence_max_attempts: int = 2
    evidence_min_quote_chars: int = 20
    evidence_max_quote_chars: int = 400
    evidence_max_rationale_chars: int = 300
