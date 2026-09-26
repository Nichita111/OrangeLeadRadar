"""[Refresh scheduling](/architecture/rules.md#refresh-scheduling): the account's refresh times
once one of its refreshes finishes, and the scheduler's selection of due accounts."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from leadradar.core.enums import AccountStatus, PipelineRunStatus


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


@dataclass(frozen=True)
class RefreshCandidate:
    """One account the scheduler tick considers: its status, `next_refresh_at`, and whether it
    already has a `QUEUED` or `RUNNING` `ACCOUNT_REFRESH`."""

    account_id: uuid.UUID
    status: AccountStatus
    next_refresh_at: datetime | None
    has_active_refresh: bool


def due_refresh_account_ids(
    candidates: Sequence[RefreshCandidate], *, now: datetime, limit: int
) -> list[uuid.UUID]:
    """The Algorithm of [Refresh scheduling](/architecture/rules.md#refresh-scheduling): the
    active accounts with no active refresh whose `next_refresh_at` is due — null (a new
    account) or at or before `now` — oldest due first, capped at `limit`
    (`SCHEDULER_MAX_ENQUEUE`). A null `next_refresh_at` sorts before every timestamp: a new
    account has been due since it was created, before any scheduled one."""
    due = [
        candidate
        for candidate in candidates
        if candidate.status is AccountStatus.ACTIVE
        and not candidate.has_active_refresh
        and (candidate.next_refresh_at is None or candidate.next_refresh_at <= now)
    ]
    due.sort(
        key=lambda candidate: (
            candidate.next_refresh_at is not None,
            candidate.next_refresh_at or now,
            str(candidate.account_id),
        )
    )
    return [candidate.account_id for candidate in due[:limit]]
