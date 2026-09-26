"""Unit tests of [`ApiSettings`](/architecture/services/api.md#runtime): required keys are
required, an unknown `FIXTURE_MODE` is refused, and a secret is never exposed by `repr`
([N-07](/requirements/system.md) part of `AC-67`)."""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr, ValidationError

from leadradar.api.settings import ApiSettings
from leadradar.logs import JsonFormatter

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
        openrouter_api_key=SecretStr("s3cret-openrouter-key"),
    )
    assert "s3cret-db-password" not in repr(settings)
    assert "s3cret-openrouter-key" not in repr(settings)
    assert "s3cret-db-password" not in str(settings)
    assert "s3cret-openrouter-key" not in str(settings)


def test_a_logged_settings_object_never_contains_the_password_or_the_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ApiSettings(
        database_url=SecretStr("postgresql://u:s3cret-db-password@localhost/db"),
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
