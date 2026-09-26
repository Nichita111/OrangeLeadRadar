"""Unit tests of the AI gateway keys of [worker Runtime](/architecture/services/worker.md#runtime),
shared by both processes' settings."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from leadradar.core.enums import DocumentTriageClassifier
from leadradar.settings import ApiSettings
from leadradar.worker.settings import WorkerSettings

pytestmark = pytest.mark.unit

_DATABASE_URL = "postgresql://u:p@localhost/db"


def test_the_gateway_keys_take_their_runtime_defaults() -> None:
    settings = WorkerSettings(database_url=SecretStr(_DATABASE_URL))

    assert settings.classifier_provider == DocumentTriageClassifier.LLM
    assert settings.jev_model == "typesafe/jev-1.13"
    assert settings.jev_decisions_url == "https://openrouter.ai/api/alpha/decisions"
    assert settings.llm_classifier_model is None
    assert settings.llm_daily_budget_eur == 20
    assert settings.classifier_timeout_s == 10
    assert settings.ai_call_timeout_s == 60
    assert settings.ai_transport_retries == 2
    assert settings.ai_transport_backoff_ms == 500
    assert settings.ai_concurrency == 8
    assert settings.usd_eur_rate == 0.92
    assert settings.fixture_mode == "off"


def test_both_processes_read_the_gateway_keys_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "JEV")
    monkeypatch.setenv("LLM_EVIDENCE_MODEL", "google/gemini-2.5-flash")
    monkeypatch.setenv("LLM_DAILY_BUDGET_EUR", "5")
    monkeypatch.setenv("FIXTURE_MODE", "replay")

    worker = WorkerSettings(database_url=SecretStr(_DATABASE_URL))
    api = ApiSettings(
        database_url=SecretStr("postgresql://u:p@localhost/db"),
        migration_database_url=SecretStr("postgresql://o:p@localhost/db"),
    )

    for settings in (worker, api):
        assert settings.classifier_provider == DocumentTriageClassifier.JEV
        assert settings.llm_evidence_model == "google/gemini-2.5-flash"
        assert settings.llm_daily_budget_eur == 5
        assert settings.fixture_mode == "replay"


def test_an_unknown_classifier_provider_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "GPT")

    with pytest.raises(ValidationError):
        WorkerSettings(database_url=SecretStr(_DATABASE_URL))
