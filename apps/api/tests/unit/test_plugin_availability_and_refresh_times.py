"""Unit tests of [Plug-in availability](/architecture/rules.md#plug-in-availability) and of the
refresh times of [Refresh scheduling](/architecture/rules.md#refresh-scheduling)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from leadradar.core.enums import PipelineRunStatus, SourcePluginCode
from leadradar.core.plugin_availability import is_plugin_available
from leadradar.core.refresh_scheduling import RefreshTimes, refresh_times_after

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
