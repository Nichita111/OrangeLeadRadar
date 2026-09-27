"""Unit tests of [Retention and erasure](/architecture/rules.md#retention-and-erasure) and
[Scheduler and housekeeping](/architecture/services/worker.md#scheduler-and-housekeeping) as
amended (G3): pure date and time math, no I/O."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from leadradar.core.retention import housekeeping_due, session_deletion_cutoff

pytestmark = pytest.mark.unit

HOUR = 3


def _at(hour: int, day: int = 27) -> datetime:
    return datetime(2026, 9, day, hour, 0, tzinfo=UTC)


class TestHousekeepingDue:
    @pytest.mark.parametrize(
        ("now", "last_day", "expected"),
        [
            pytest.param(_at(HOUR - 1), None, False, id="not_due_before_the_hour"),
            pytest.param(_at(HOUR), None, True, id="due_at_the_hour_when_never_run"),
            pytest.param(
                _at(HOUR + 5),
                date(2026, 9, 26),
                True,
                id="due_later_the_same_day_when_it_has_not_run_that_day",
            ),
            pytest.param(_at(HOUR), date(2026, 9, 27), False, id="not_due_again_the_same_day"),
            pytest.param(_at(HOUR, day=28), date(2026, 9, 27), True, id="due_the_next_day"),
            pytest.param(_at(HOUR + 2), None, True, id="due_at_the_first_tick_of_a_fresh_process"),
        ],
    )
    def test_housekeeping_due(self, now: datetime, last_day: date | None, expected: bool) -> None:
        assert housekeeping_due(now, HOUR, last_day) is expected


class TestSessionDeletionCutoff:
    def test_a_session_exactly_the_ttl_old_is_kept(self) -> None:
        now = _at(HOUR)
        cutoff = session_deletion_cutoff(now, session_ttl_hours=12)
        expired_at = now - timedelta(hours=12)
        assert not (expired_at < cutoff)

    def test_a_session_one_second_older_than_the_ttl_is_deleted(self) -> None:
        now = _at(HOUR)
        cutoff = session_deletion_cutoff(now, session_ttl_hours=12)
        expired_at = now - timedelta(hours=12, seconds=1)
        assert expired_at < cutoff
