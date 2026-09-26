"""[Budget guard](/architecture/rules.md#budget-guard): whether an LLM call may be made, the day
its spend is summed over, and a call's cost in euros. No I/O and no clock: `now` and the spend
arrive as arguments."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta


def budget_day_start(now: datetime) -> datetime:
    """00:00 UTC of `now`'s day: the spend is summed from here."""
    return datetime.combine(now.astimezone(UTC).date(), time(0), tzinfo=UTC)


def budget_resets_at(now: datetime) -> datetime:
    """The next 00:00 UTC after `now`: `details.resets_at` of `BUDGET_EXHAUSTED`."""
    return budget_day_start(now) + timedelta(days=1)


def is_budget_exhausted(*, spent_today_eur: float, daily_budget_eur: float) -> bool:
    """True once today's spend has reached `LLM_DAILY_BUDGET_EUR`: no further LLM call."""
    return spent_today_eur >= daily_budget_eur


def call_cost_eur(*, usage_cost_usd: float | None, usd_eur_rate: float) -> float:
    """`cost_eur` of an AI call: the `usage.cost` OpenRouter returns, in US dollars, at
    `USD_EUR_RATE`. A response that carries no cost (a timeout, an error) adds nothing to the
    spend."""
    if usage_cost_usd is None:
        return 0.0
    return usage_cost_usd * usd_eur_rate
