"""Unit tests of [Fetch window](/architecture/rules.md#fetch-window) (`S-ING-02`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from leadradar.core.fetch_window import fetch_window, news_queries_by_service, news_query

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def test_fetch_window_defaults_to_the_lookback_period() -> None:
    window = fetch_window(now=_NOW, lookback_days=365, newest_published_at=None)
    assert window.since == _NOW - timedelta(days=365)
    assert window.until == _NOW


def test_fetch_window_lower_bound_is_raised_to_one_day_before_the_newest_document() -> None:
    newest = _NOW - timedelta(days=10)
    window = fetch_window(now=_NOW, lookback_days=365, newest_published_at=newest)
    assert window.since == newest - timedelta(days=1)


def test_fetch_window_never_narrower_than_it_would_otherwise_be() -> None:
    # A "newest document" older than the lookback window does not widen it backwards.
    ancient = _NOW - timedelta(days=1000)
    window = fetch_window(now=_NOW, lookback_days=365, newest_published_at=ancient)
    assert window.since == _NOW - timedelta(days=365)


def test_news_query_without_hint_terms_is_the_name_alone() -> None:
    assert news_query(name="DHL Group", aliases=[], hint_terms=[]) == '"DHL Group"'


def test_news_query_combines_name_aliases_and_hint_terms() -> None:
    query = news_query(name="DHL Group", aliases=["DHL"], hint_terms=["automation", "RPA"])
    assert query == '("DHL Group" OR "DHL") ("automation" OR "RPA")'


def test_news_queries_by_service_keys_one_query_per_service() -> None:
    queries = news_queries_by_service(
        name="DHL Group",
        aliases=[],
        hint_terms_by_service={"svc-1": ["automation"], "svc-2": []},
    )
    assert queries == {"svc-1": '("DHL Group") ("automation")', "svc-2": '"DHL Group"'}
