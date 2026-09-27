"""Configuration of the worker process: [worker Runtime](/architecture/services/worker.md#runtime).
Only the keys the worker's code reads today are here, with `DATABASE_URL` of the
[api Runtime](/architecture/services/api.md#runtime) that the job loop reads, and the keys the
SCORE and SIGNAL steps read."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from leadradar.ai.settings import AiGatewaySettings
from leadradar.logs import LogLevel


class WorkerSettings(AiGatewaySettings):
    """The worker process's configuration; fixture mode, `CLOCK_FILE` and the AI gateway's keys
    come from `AiGatewaySettings`."""

    model_config = SettingsConfigDict(extra="ignore")

    log_level: LogLevel = "INFO"

    database_url: SecretStr
    worker_concurrency: int = 4
    job_max_attempts: int = 3
    job_retry_backoff_s: int = 30
    job_lock_timeout_s: int = 900
    job_poll_interval_s: int = 1
    refresh_interval_hours: int = 24
    scheduler_tick_s: int = 60
    scheduler_max_enqueue: int = 20
    housekeeping_hour_utc: int = 3
    refresh_target_minutes: int = 10

    #: [Plug-in availability](/architecture/rules.md#plug-in-availability): unset by default;
    #: a plug-in whose key is unset is unavailable. Declared here too, as `DATABASE_URL` is,
    #: for the scheduler's own enqueueing of a refresh's first jobs.
    crunchbase_api_key: SecretStr | None = None
    newsapi_key: SecretStr | None = None
    serpapi_key: SecretStr | None = None

    #: Alert window ([Alerts](/architecture/rules.md#alerts))
    alert_max_age_days: int = 14
    discovery_max_candidates: int = 50
    discovery_lookback_days: int = 30
    discovery_max_documents: int = 100

    # SIGNAL step ([worker Configuration](/architecture/services/worker.md#runtime));
    # `escalation_lower`, `escalation_upper` and `triage_relevance_min_p` come from
    # `AiGatewaySettings`, read by the api as well (D7).
    triage_chars: int = 2000
    triage_about_min_p: float = 0.5
    evidence_max_attempts: int = 2
    evidence_min_quote_chars: int = 20
    evidence_max_quote_chars: int = 400
    evidence_max_rationale_chars: int = 300
    #: Fetching and processing ([worker Runtime](/architecture/services/worker.md#runtime)).
    fetch_lookback_days: int = 365
    max_documents_per_refresh: int = 100
    crawl_max_pages_per_site: int = 30
    crawl_max_pdfs: int = 3
    crawl_host_delay_ms: int = 1000
    crawler_user_agent: str | None = None
    website_render_js: bool = False
    http_timeout_s: float = 20.0
    gdelt_max_records: int = 250
    gdelt_min_interval_s: float = 6.0
    gdelt_backoff_s: int = 60
    min_document_chars: int = 200
    whole_document_max_chars: int = 8000
    chunk_target_chars: int = 1600
    chunk_overlap_chars: int = 200
    passages_per_question: int = 3
    max_passages_per_document: int = 20
    retrieval_candidates: int = 50
    retrieval_rrf_k: int = 60
    near_duplicate_similarity: float = 0.95
    near_duplicate_window_days: int = 7
    document_retention_days: int = 730

    # EVALUATE step ([Evaluation metrics](/architecture/rules.md#evaluation-metrics),
    # [worker Runtime](/architecture/services/worker.md#runtime)); `eval_min_items` comes from
    # `AiGatewaySettings`, read by the api as well.
    eval_min_precision: float = 0.80
    escalation_rate_target: float = 0.15
    eval_classifier_only_p: float = 0.5
    eval_calibration_bins: int = 10
    eval_max_errors: int = 50

    def crawler_user_agent_or_default(self) -> str:
        """`CRAWLER_USER_AGENT`'s default names `APP_BASE_URL`, so an unset override is resolved
        against it rather than baked into a second literal."""
        return self.crawler_user_agent or f"LeadRadar/0.1 (+{self.app_base_url}/crawler)"
