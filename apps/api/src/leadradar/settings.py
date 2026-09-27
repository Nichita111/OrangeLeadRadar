"""Configuration of the api process: [api Runtime](/architecture/services/api.md#runtime)
and the [worker Runtime](/architecture/services/worker.md#runtime) keys the api's health
checks read. Read once at start and passed in; no other module reads the environment.

Lives beside `core`, `db`, `api`, `audit` and `worker` rather than inside `api/` (a router
package) because a capability package (`audit`) also needs it: `api` importing `audit`, and
`audit` importing back from `api`, would be a layering cycle
([Coding Structure](/guidelines/coding.md#structure))."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from leadradar.ai.settings import AiGatewaySettings
from leadradar.logs import LogLevel


class ApiSettings(AiGatewaySettings):
    """The api process's configuration; fixture mode, `CLOCK_FILE` and the AI gateway's keys
    come from `AiGatewaySettings`."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: SecretStr
    migration_database_url: SecretStr
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: LogLevel = "INFO"
    health_timeout_ms: int = 2000

    impact_period_days: int = 30
    manual_research_minutes_per_account: int = 120
    app_base_url: str = "http://localhost:8080"
    hubspot_timeout_s: float = 10
    session_ttl_hours: int = 12
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    password_min_length: int = 12

    page_size_default: int = 50
    page_size_max: int = 200
    crunchbase_api_key: SecretStr | None = None
    newsapi_key: SecretStr | None = None
    serpapi_key: SecretStr | None = None
    import_max_rows: int = 2000
    audit_default_range_days: int = 30
    preview_max_passages: int = 5
    label_queue_size: int = 20
    outreach_max_findings: int = 5
    provider_facts_per_call: int = 8
    prospect_top_signals: int = 2
    hubspot_top_signals: int = 3
    outreach_email_max_chars: int = 1200
    outreach_inmail_max_chars: int = 1900
    contact_retention_days: int = 730
    contact_suggestion_max_passages: int = 8
    contact_suggestion_max: int = 10
    hubspot_access_token: SecretStr | None = None
    job_poll_interval_s: int = 1
    refresh_target_minutes: int = 10
