"""Unit tests of crawl pacing (`N-09`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from leadradar.core.crawl_pacing import seconds_to_wait

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)


def test_no_previous_request_needs_no_wait() -> None:
    assert seconds_to_wait(last_request_at=None, now=_NOW, delay_ms=1000) == 0.0


def test_elapsed_time_just_below_the_delay_still_waits() -> None:
    last = _NOW - timedelta(milliseconds=999)
    assert seconds_to_wait(last_request_at=last, now=_NOW, delay_ms=1000) == pytest.approx(0.001)


def test_elapsed_time_at_the_delay_needs_no_wait() -> None:
    last = _NOW - timedelta(milliseconds=1000)
    assert seconds_to_wait(last_request_at=last, now=_NOW, delay_ms=1000) == 0.0


def test_elapsed_time_past_the_delay_needs_no_wait() -> None:
    last = _NOW - timedelta(seconds=5)
    assert seconds_to_wait(last_request_at=last, now=_NOW, delay_ms=1000) == 0.0
