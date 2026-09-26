"""Unit tests of `clock.now`: [api Runtime](/architecture/services/api.md#runtime),
[worker Runtime](/architecture/services/worker.md#runtime), [Fixture mode]
(/architecture/overview.md#runtime)."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest

from leadradar.clock import now

pytestmark = pytest.mark.unit


def test_replay_with_a_clock_file_returns_that_files_time_in_utc(tmp_path: Path) -> None:
    clock_file = tmp_path / "now.txt"
    clock_file.write_text("2026-01-01T12:00:00Z")

    result = now(fixture_mode="replay", clock_file=clock_file)

    assert result.tzinfo is not None
    assert result.astimezone(UTC).isoformat() == "2026-01-01T12:00:00+00:00"


def test_replay_rereads_the_file_after_it_changes(tmp_path: Path) -> None:
    clock_file = tmp_path / "now.txt"
    clock_file.write_text("2026-01-01T12:00:00Z")
    first = now(fixture_mode="replay", clock_file=clock_file)

    clock_file.write_text("2026-01-02T00:00:00Z")
    second = now(fixture_mode="replay", clock_file=clock_file)

    assert first != second
    assert second.astimezone(UTC).isoformat() == "2026-01-02T00:00:00+00:00"


def test_fixture_mode_off_ignores_clock_file_and_uses_the_system_clock(tmp_path: Path) -> None:
    clock_file = tmp_path / "now.txt"
    clock_file.write_text("2000-01-01T00:00:00Z")

    result = now(fixture_mode="off", clock_file=clock_file)

    assert result.year > 2000


def test_fixture_mode_record_ignores_clock_file_and_uses_the_system_clock(tmp_path: Path) -> None:
    clock_file = tmp_path / "now.txt"
    clock_file.write_text("2000-01-01T00:00:00Z")

    result = now(fixture_mode="record", clock_file=clock_file)

    assert result.year > 2000


def test_replay_with_a_missing_file_raises_rather_than_falling_back(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.txt"

    with pytest.raises(FileNotFoundError):
        now(fixture_mode="replay", clock_file=missing)


def test_replay_with_a_malformed_file_raises_rather_than_falling_back(tmp_path: Path) -> None:
    clock_file = tmp_path / "now.txt"
    clock_file.write_text("not-a-timestamp")

    with pytest.raises(ValueError, match="not-a-timestamp"):
        now(fixture_mode="replay", clock_file=clock_file)


def test_replay_with_no_clock_file_uses_the_system_clock() -> None:
    result = now(fixture_mode="replay", clock_file=None)

    assert result.year > 2000
