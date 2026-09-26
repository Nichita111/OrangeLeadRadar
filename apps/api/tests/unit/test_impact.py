"""Unit tests of [Impact](/architecture/rules.md#impact): `compute_impact`."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from leadradar.core.impact import ImpactInputs, compute_impact

pytestmark = pytest.mark.unit


def make_inputs(**overrides: Any) -> ImpactInputs:
    defaults: dict[str, Any] = {
        "refreshes": 4,
        "accounts_refreshed": 3,
        "total_ai_call_cost_eur": 4.0,
        "total_run_duration": timedelta(minutes=8),
        "findings_created": 5,
        "latest_passing_precision": 0.9,
        "latest_passing_labelled_items": 250,
        "period_days": 30,
        "manual_minutes_per_account": 120,
    }
    defaults.update(overrides)
    return ImpactInputs(**defaults)


def test_several_refreshes_of_the_same_account_give_fewer_accounts_than_refreshes() -> None:
    report = compute_impact(make_inputs(refreshes=4, accounts_refreshed=3))

    assert report.refreshes == 4
    assert report.accounts_refreshed == 3


def test_cost_per_refresh_is_total_cost_divided_by_refreshes_to_two_decimals() -> None:
    report = compute_impact(make_inputs(refreshes=3, total_ai_call_cost_eur=1.0))

    assert report.cost_per_refresh_eur == pytest.approx(0.33)


def test_runs_with_no_ai_call_cost_give_zero_not_null() -> None:
    report = compute_impact(make_inputs(refreshes=2, total_ai_call_cost_eur=0.0))

    assert report.cost_per_refresh_eur == 0.0


def test_no_runs_gives_null_cost_null_minutes_and_zero_counts() -> None:
    report = compute_impact(
        make_inputs(
            refreshes=0,
            accounts_refreshed=0,
            total_ai_call_cost_eur=0.0,
            total_run_duration=timedelta(),
            findings_created=0,
        )
    )

    assert report.cost_per_refresh_eur is None
    assert report.minutes_per_refresh is None
    assert report.accounts_refreshed == 0
    assert report.refreshes == 0
    assert report.findings_created == 0
    assert report.manual_hours_replaced == 0.0


def test_minutes_per_refresh_is_the_mean_duration_in_minutes_to_two_decimals() -> None:
    report = compute_impact(make_inputs(refreshes=3, total_run_duration=timedelta(minutes=10)))

    assert report.minutes_per_refresh == pytest.approx(3.33)


def test_manual_hours_replaced_is_accounts_refreshed_times_minutes_over_sixty() -> None:
    report = compute_impact(make_inputs(accounts_refreshed=5, manual_minutes_per_account=120))

    assert report.manual_hours_replaced == pytest.approx(10.0)


def test_without_a_passing_evaluation_precision_and_labelled_items_are_null() -> None:
    report = compute_impact(
        make_inputs(latest_passing_precision=None, latest_passing_labelled_items=None)
    )

    assert report.precision is None
    assert report.labelled_items is None
    assert report.refreshes == 4
    assert report.accounts_refreshed == 3
    assert report.findings_created == 5


def test_a_third_decimal_of_five_rounds_half_up_and_integer_fields_stay_integers() -> None:
    report = compute_impact(
        make_inputs(
            refreshes=8,
            total_ai_call_cost_eur=1.0,
            total_run_duration=timedelta(minutes=1),
        )
    )

    # 1.0 / 8 = 0.125 -> half up to 0.13, not the 0.12 banker's rounding would give.
    assert report.cost_per_refresh_eur == 0.13
    assert isinstance(report.refreshes, int)
    assert isinstance(report.accounts_refreshed, int)
    assert isinstance(report.findings_created, int)


def test_period_days_and_manual_minutes_per_account_echo_the_inputs() -> None:
    report = compute_impact(make_inputs(period_days=45, manual_minutes_per_account=90))

    assert report.period_days == 45
    assert report.manual_minutes_per_account == 90
