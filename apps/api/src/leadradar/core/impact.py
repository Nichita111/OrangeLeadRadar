"""[Impact](/architecture/rules.md#impact) (`S-EVL-05`, `API-77`): a pure function of the
aggregates `evaluation.impact.read_impact` gathers. No I/O, no clock: `period_days` and
`manual_minutes_per_account` arrive already resolved from configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal


def _round_half_up(value: float) -> float:
    """Rounds to two decimals, half up, per the [Rules](/architecture/rules.md) preamble."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class ImpactInputs:
    """The Inputs of [Impact](/architecture/rules.md#impact), already aggregated by
    `evaluation.impact.read_impact`."""

    refreshes: int
    accounts_refreshed: int
    total_ai_call_cost_eur: float
    total_run_duration: timedelta
    findings_created: int
    latest_passing_precision: float | None
    latest_passing_labelled_items: int | None
    period_days: int
    manual_minutes_per_account: int


@dataclass(frozen=True)
class ImpactReport:
    """[`Impact`](/architecture/interfaces.md#impact), the response of `API-77`."""

    period_days: int
    accounts_refreshed: int
    refreshes: int
    cost_per_refresh_eur: float | None
    minutes_per_refresh: float | None
    findings_created: int
    precision: float | None
    labelled_items: int | None
    manual_minutes_per_account: int
    manual_hours_replaced: float


def compute_impact(inputs: ImpactInputs) -> ImpactReport:
    """The algorithm row of [Impact](/architecture/rules.md#impact)."""
    has_runs = inputs.refreshes > 0
    cost_per_refresh_eur = (
        _round_half_up(inputs.total_ai_call_cost_eur / inputs.refreshes) if has_runs else None
    )
    minutes_per_refresh = (
        _round_half_up(inputs.total_run_duration.total_seconds() / 60 / inputs.refreshes)
        if has_runs
        else None
    )
    manual_hours_replaced = _round_half_up(
        inputs.accounts_refreshed * inputs.manual_minutes_per_account / 60
    )
    return ImpactReport(
        period_days=inputs.period_days,
        accounts_refreshed=inputs.accounts_refreshed,
        refreshes=inputs.refreshes,
        cost_per_refresh_eur=cost_per_refresh_eur,
        minutes_per_refresh=minutes_per_refresh,
        findings_created=inputs.findings_created,
        precision=inputs.latest_passing_precision,
        labelled_items=inputs.latest_passing_labelled_items,
        manual_minutes_per_account=inputs.manual_minutes_per_account,
        manual_hours_replaced=manual_hours_replaced,
    )
