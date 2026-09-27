"""Unit test of [`clock.py`](/architecture/services/worker.md#runtime) `CLOCK_FILE`."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from leadradar.clock import build_clock
from leadradar.settings import ApiSettings

pytestmark = pytest.mark.unit


def _settings(**overrides: Any) -> ApiSettings:
    defaults: dict[str, Any] = {
        "database_url": SecretStr("postgresql://u:p@localhost/db"),
        "migration_database_url": SecretStr("postgresql://u:p@localhost/db"),
    }
    defaults.update(overrides)
    return ApiSettings(**defaults)


@pytest.mark.parametrize("mode", ["record", "replay"])
def test_clock_reads_clock_file_on_every_call_in_record_and_replay(
    tmp_path: Path, mode: str
) -> None:
    clock_file = tmp_path / "clock"
    clock_file.write_text("2026-01-01T00:00:00Z")

    clock = build_clock(_settings(fixture_mode=mode, clock_file=clock_file))
    assert clock() == datetime.fromisoformat("2026-01-01T00:00:00+00:00")

    clock_file.write_text("2026-06-15T12:30:00Z")
    assert clock() == datetime.fromisoformat("2026-06-15T12:30:00+00:00")


def test_clock_ignores_clock_file_in_off_or_when_unset(tmp_path: Path) -> None:
    clock_file = tmp_path / "clock"
    clock_file.write_text("2026-06-15T12:30:00Z")

    off_mode = build_clock(_settings(fixture_mode="off", clock_file=clock_file))
    assert off_mode() != datetime.fromisoformat("2026-06-15T12:30:00+00:00")

    unset_clock_file = build_clock(_settings(fixture_mode="replay", clock_file=None))
    assert unset_clock_file() != datetime.fromisoformat("2026-06-15T12:30:00+00:00")
