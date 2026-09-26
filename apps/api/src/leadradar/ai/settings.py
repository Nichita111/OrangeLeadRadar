"""The keys of the [AI gateway and embedder](/architecture/services/worker.md#runtime) group,
"read by the api as well", and of [fixture mode](/architecture/overview.md#runtime) with the
`CLOCK_FILE` it governs. Both processes' settings classes extend this one, so each key is
declared once; the gateway takes it without knowing which process it runs in."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from leadradar.core.enums import DocumentTriageClassifier

FixtureMode = Literal["off", "record", "replay"]


class AiGatewaySettings(BaseSettings):
    """Fixture mode and the AI gateway's keys, with their Runtime defaults."""

    model_config = SettingsConfigDict(extra="ignore")

    fixture_mode: FixtureMode = "off"
    fixture_dir: Path = Path("./fixtures")
    clock_file: Path | None = None

    classifier_provider: DocumentTriageClassifier = DocumentTriageClassifier.LLM
    jev_model: str = "typesafe/jev-1.13"
    jev_decisions_url: str = "https://openrouter.ai/api/alpha/decisions"
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_classifier_model: str | None = None
    llm_evidence_model: str | None = None
    llm_outreach_model: str | None = None
    llm_daily_budget_eur: float = 20.0
    classifier_timeout_s: float = 10.0
    ai_call_timeout_s: float = 60.0
    ai_transport_retries: int = 2
    ai_transport_backoff_ms: int = 500
    ai_concurrency: int = 8
    usd_eur_rate: float = 0.92
