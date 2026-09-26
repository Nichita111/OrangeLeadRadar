"""[Refresh scheduling](/architecture/rules.md#refresh-scheduling): the account's refresh times
once one of its refreshes finishes. The scheduler's selection of due accounts belongs here too
when it is built."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from leadradar.core.enums import PipelineRunStatus


@dataclass(frozen=True)
class RefreshTimes:
    """The account's new `next_refresh_at`, and its new `last_refreshed_at` or `None` to keep
    the one it has."""

    next_refresh_at: datetime
    last_refreshed_at: datetime | None


def refresh_times_after(
    status: PipelineRunStatus, finished_at: datetime, *, refresh_interval_hours: int
) -> RefreshTimes | None:
    """After a refresh finishes in `status`: `next_refresh_at` = `finished_at` +
    `REFRESH_INTERVAL_HOURS`, and `last_refreshed_at` = `finished_at` unless it `FAILED`;
    `None` — nothing changes — for a `CANCELLED` refresh."""
    if status is PipelineRunStatus.CANCELLED:
        return None
    return RefreshTimes(
        next_refresh_at=finished_at + timedelta(hours=refresh_interval_hours),
        last_refreshed_at=None if status is PipelineRunStatus.FAILED else finished_at,
    )
