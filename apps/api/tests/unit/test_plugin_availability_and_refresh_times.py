"""Unit tests of [Plug-in availability](/architecture/rules.md#plug-in-availability) and of the
refresh times and due-account selection of
[Refresh scheduling](/architecture/rules.md#refresh-scheduling)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from leadradar.core.enums import AccountStatus, PipelineRunStatus, SourcePluginCode
from leadradar.core.plugin_availability import is_plugin_available
from leadradar.core.refresh_scheduling import (
    RefreshCandidate,
    RefreshTimes,
    due_refresh_account_ids,
    refresh_times_after,
)

pytestmark = pytest.mark.unit

_FINISHED = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("code", "enabled", "key_configured", "requests_today", "daily_quota", "expected"),
    [
        (SourcePluginCode.GDELT, True, False, 0, None, True),
        (SourcePluginCode.GDELT, False, False, 0, None, False),
        (SourcePluginCode.CRUNCHBASE, True, False, 0, 200, False),
        (SourcePluginCode.CRUNCHBASE, True, True, 0, 200, True),
        (SourcePluginCode.NEWSAPI, True, True, 99, 100, True),
        (SourcePluginCode.NEWSAPI, True, True, 100, 100, False),
        (SourcePluginCode.SERPAPI, True, False, 0, None, False),
    ],
)
def test_is_plugin_available(
    code: SourcePluginCode,
    enabled: bool,
    key_configured: bool,
    requests_today: int,
    daily_quota: int | None,
    expected: bool,
) -> None:
    assert (
        is_plugin_available(
            code=code,
            enabled=enabled,
            key_configured=key_configured,
            requests_today=requests_today,
            daily_quota=daily_quota,
        )
        is expected
    )


@pytest.mark.parametrize("status", [PipelineRunStatus.SUCCEEDED, PipelineRunStatus.PARTIAL])
def test_a_finished_refresh_sets_both_times(status: PipelineRunStatus) -> None:
    assert refresh_times_after(status, _FINISHED, refresh_interval_hours=24) == RefreshTimes(
        next_refresh_at=_FINISHED + timedelta(hours=24), last_refreshed_at=_FINISHED
    )


def test_a_failed_refresh_keeps_last_refreshed_at() -> None:
    assert refresh_times_after(
        PipelineRunStatus.FAILED, _FINISHED, refresh_interval_hours=24
    ) == RefreshTimes(next_refresh_at=_FINISHED + timedelta(hours=24), last_refreshed_at=None)


def test_a_cancelled_refresh_changes_nothing() -> None:
    assert (
        refresh_times_after(PipelineRunStatus.CANCELLED, _FINISHED, refresh_interval_hours=24)
        is None
    )


_NOW = datetime(2026, 9, 26, 0, 0, tzinfo=UTC)


def _candidate(
    *,
    status: AccountStatus = AccountStatus.ACTIVE,
    next_refresh_at: datetime | None,
    has_active_refresh: bool = False,
    account_id: uuid.UUID | None = None,
) -> RefreshCandidate:
    return RefreshCandidate(
        account_id=account_id or uuid.uuid4(),
        status=status,
        next_refresh_at=next_refresh_at,
        has_active_refresh=has_active_refresh,
    )


def test_due_account_selection_excludes_inactive_and_active_refresh_and_not_yet_due() -> None:
    # AC-29: three active accounts due and one inactive account due.
    due_a = _candidate(next_refresh_at=_NOW - timedelta(hours=1))
    due_b = _candidate(next_refresh_at=_NOW)
    due_new = _candidate(next_refresh_at=None)
    inactive_due = _candidate(
        status=AccountStatus.INACTIVE, next_refresh_at=_NOW - timedelta(hours=1)
    )
    not_yet_due = _candidate(next_refresh_at=_NOW + timedelta(hours=1))
    already_refreshing = _candidate(
        next_refresh_at=_NOW - timedelta(hours=1), has_active_refresh=True
    )

    selected = due_refresh_account_ids(
        [due_a, due_b, due_new, inactive_due, not_yet_due, already_refreshing], now=_NOW, limit=20
    )

    assert set(selected) == {due_a.account_id, due_b.account_id, due_new.account_id}


def test_due_account_selection_orders_oldest_due_first_and_caps_at_limit() -> None:
    newest_due = _candidate(next_refresh_at=_NOW - timedelta(hours=1))
    oldest_due = _candidate(next_refresh_at=_NOW - timedelta(hours=5))
    never_refreshed = _candidate(next_refresh_at=None)

    selected = due_refresh_account_ids([newest_due, oldest_due, never_refreshed], now=_NOW, limit=2)

    assert selected == [never_refreshed.account_id, oldest_due.account_id]
