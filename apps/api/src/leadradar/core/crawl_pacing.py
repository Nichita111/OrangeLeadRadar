"""Crawl etiquette pacing (`N-09`, [Fetch window](/architecture/rules.md#fetch-window)): how long
a crawler still owes before another request to the same host, or to a rate-limited provider such
as GDELT. Pure function of the last request's time and now; the caller owns the clock and the
sleep."""

from __future__ import annotations

from datetime import datetime


def seconds_to_wait(*, last_request_at: datetime | None, now: datetime, delay_ms: int) -> float:
    """`0` when there is no previous request or `delay_ms` has already elapsed since it; else
    the remaining seconds, so `CRAWL_HOST_DELAY_MS` (or a plug-in's own pacing, in the same
    shape) is honoured between consecutive requests."""
    if last_request_at is None:
        return 0.0
    elapsed_ms = (now - last_request_at).total_seconds() * 1000
    return max(0.0, (delay_ms - elapsed_ms) / 1000)
