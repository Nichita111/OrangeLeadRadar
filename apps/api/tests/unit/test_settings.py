"""Unit tests of [`ApiSettings`](/architecture/services/api.md#runtime): required keys are
required, an unknown `FIXTURE_MODE` is refused, and a secret is never exposed by `repr`
([N-07](/requirements/system.md) part of `AC-67`)."""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr, ValidationError

from leadradar.logs import JsonFormatter
from leadradar.settings import ApiSettings

pytestmark = pytest.mark.unit


def test_settings_refuse_to_start_without_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        ApiSettings()
    assert "database_url" in str(excinfo.value).lower()


def test_settings_reject_an_unknown_fixture_mode() -> None:
    with pytest.raises(ValidationError):
        ApiSettings.model_validate(
            {
                "database_url": "postgresql://u:p@localhost/db",
                "fixture_mode": "bogus",
            }
        )


def test_repr_of_settings_never_contains_the_password_or_the_openrouter_key() -> None:
    settings = ApiSettings(
        database_url=SecretStr("postgresql://u:s3cret-db-password@localhost/db"),
        migration_database_url=SecretStr("postgresql://u:s3cret-db-password@localhost/db"),
        openrouter_api_key=SecretStr("s3cret-openrouter-key"),
    )
    assert "s3cret-db-password" not in repr(settings)
    assert "s3cret-openrouter-key" not in repr(settings)
    assert "s3cret-db-password" not in str(settings)
    assert "s3cret-openrouter-key" not in str(settings)


def test_impact_and_clock_keys_take_their_runtime_defaults() -> None:
    settings = ApiSettings(
        database_url=SecretStr("postgresql://u:p@localhost/db"),
        migration_database_url=SecretStr("postgresql://o:p@localhost/db"),
    )

    assert settings.impact_period_days == 30
    assert settings.manual_research_minutes_per_account == 120
    assert settings.clock_file is None


def test_impact_and_clock_keys_are_overridden_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://o:p@localhost/db")
    monkeypatch.setenv("IMPACT_PERIOD_DAYS", "14")
    monkeypatch.setenv("MANUAL_RESEARCH_MINUTES_PER_ACCOUNT", "90")
    monkeypatch.setenv("CLOCK_FILE", "/tmp/now.txt")

    settings = ApiSettings()

    assert settings.impact_period_days == 14
    assert settings.manual_research_minutes_per_account == 90
    assert str(settings.clock_file) == "/tmp/now.txt"


def test_a_logged_settings_object_never_contains_the_password_or_the_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ApiSettings(
        database_url=SecretStr("postgresql://u:s3cret-db-password@localhost/db"),
        migration_database_url=SecretStr("postgresql://u:s3cret-db-password@localhost/db"),
        openrouter_api_key=SecretStr("s3cret-openrouter-key"),
    )
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="settings: %s",
        args=(settings,),
        exc_info=None,
    )
    formatted = JsonFormatter().format(record)
    assert "s3cret-db-password" not in formatted
    assert "s3cret-openrouter-key" not in formatted
