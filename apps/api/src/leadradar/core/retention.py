"""[Retention and erasure](/architecture/rules.md#retention-and-erasure) and [Scheduler and
housekeeping](/architecture/services/worker.md#scheduler-and-housekeeping) as amended (G3, G4):
pure date and time math over a UTC clock. No I/O."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta


def today_utc(now: datetime) -> date:
    """The clock's UTC calendar date."""
    return now.astimezone(UTC).date()


def housekeeping_due(now: datetime, hour_utc: int, last_day: date | None) -> bool:
    """Due at the first tick of each UTC day at or after `hour_utc`: not yet that hour today, or
    already run today, answers `False`; `last_day` is `None` before the process has ever run it
    (G3)."""
    if now.astimezone(UTC).hour < hour_utc:
        return False
    return last_day is None or last_day < today_utc(now)


def session_deletion_cutoff(now: datetime, session_ttl_hours: int) -> datetime:
    """[Retention and erasure]: an `auth_session` that expired or was revoked before this
    instant is deleted."""
    return now - timedelta(hours=session_ttl_hours)
