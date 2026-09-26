"""[Fetch window](/architecture/rules.md#fetch-window) (`S-ING-02`): the date range a refresh
asks a plug-in for, and the news query a service's hint terms build. Pure functions of their
inputs; the account's existing documents are read by the caller."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class FetchWindow:
    """The `since`/`until` bounds one plug-in is asked for."""

    since: datetime
    until: datetime


def fetch_window(
    *, now: datetime, lookback_days: int, newest_published_at: datetime | None
) -> FetchWindow:
    """The last `lookback_days` (`FETCH_LOOKBACK_DAYS`), with its lower bound raised to one day
    before the plug-in's newest fetched document, so a refresh asks only for new items."""
    lower = now - timedelta(days=lookback_days)
    if newest_published_at is not None:
        raised = newest_published_at - timedelta(days=1)
        if raised > lower:
            lower = raised
    return FetchWindow(since=lower, until=now)


def news_query(*, name: str, aliases: Sequence[str], hint_terms: Sequence[str]) -> str:
    """One news query for a service: the account's name or any alias, combined with `hint_terms`
    of the service's active questions whose `source_types` include `NEWS`; no terms queries the
    name alone."""
    names = " OR ".join(f'"{candidate}"' for candidate in (name, *aliases))
    if not hint_terms:
        return names
    terms = " OR ".join(f'"{term}"' for term in hint_terms)
    return f"({names}) ({terms})"


def news_queries_by_service(
    *, name: str, aliases: Sequence[str], hint_terms_by_service: Mapping[str, Sequence[str]]
) -> dict[str, str]:
    """[Fetch window](/architecture/rules.md#fetch-window) step 2: one query per active service,
    keyed by `service_id`."""
    return {
        service_id: news_query(name=name, aliases=aliases, hint_terms=terms)
        for service_id, terms in hint_terms_by_service.items()
    }
