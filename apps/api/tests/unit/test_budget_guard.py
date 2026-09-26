"""Unit tests of [Budget guard](/architecture/rules.md#budget-guard): the day window, the cap at,
just below and just above `LLM_DAILY_BUDGET_EUR`, and a call's cost at `USD_EUR_RATE`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from leadradar.core.budget_guard import (
    budget_day_start,
    budget_resets_at,
    call_cost_eur,
    is_budget_exhausted,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("spent", "exhausted"),
    [(19.99, False), (20.0, True), (20.01, True), (0.0, False)],
)
def test_the_budget_is_exhausted_once_the_spend_reaches_the_cap(
    spent: float, exhausted: bool
) -> None:
    assert is_budget_exhausted(spent_today_eur=spent, daily_budget_eur=20.0) is exhausted


def test_the_day_starts_at_midnight_utc_whatever_the_offset_of_now() -> None:
    berlin_morning = datetime(2026, 9, 26, 1, 30, tzinfo=timezone(timedelta(hours=2)))

    assert budget_day_start(berlin_morning) == datetime(2026, 9, 25, tzinfo=UTC)
    assert budget_resets_at(berlin_morning) == datetime(2026, 9, 26, tzinfo=UTC)


def test_the_budget_resets_at_the_next_midnight_utc() -> None:
    just_before = datetime(2026, 9, 26, 23, 59, 59, tzinfo=UTC)
    at_midnight = datetime(2026, 9, 27, tzinfo=UTC)

    assert budget_resets_at(just_before) == at_midnight
    assert budget_day_start(at_midnight) == at_midnight
    assert budget_resets_at(at_midnight) == datetime(2026, 9, 28, tzinfo=UTC)


def test_a_calls_cost_is_its_usage_cost_in_usd_at_the_rate() -> None:
    assert call_cost_eur(usage_cost_usd=0.5, usd_eur_rate=0.92) == pytest.approx(0.46)


def test_a_call_that_reports_no_cost_adds_nothing() -> None:
    assert call_cost_eur(usage_cost_usd=None, usd_eur_rate=0.92) == 0.0
