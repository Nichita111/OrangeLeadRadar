"""The search half of [Source plug-ins](/architecture/interfaces.md#source-plug-ins) (`API-69`):
each adapter searches for organisations (`CRUNCHBASE`) or news items (`GDELT`, `NEWSAPI`,
`SERPAPI`). [Discovery](/architecture/rules.md#discovery) (`leadradar.discovery.pipeline`) is the
search port's only caller today; fetching (`API-68`) is a different task's. An adapter absent
from a registry is never searched, so discovery finds no candidates from it until that plug-in's
task registers one line here — the same convention [`worker.steps`](steps.py) `STEP_HANDLERS`
uses for a step with no handler yet."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from leadradar.core.enums import DocumentSourceType, SourcePluginCode


@dataclass(frozen=True)
class RawNewsItem:
    """One news result of a [`NewsSearchAdapter`](#newssearchadapter): the fields [Document
    normalisation](/architecture/rules.md#document-normalisation) needs to store it as a
    [`document`](/architecture/sql-store.md#document) row, and the text already extracted."""

    url: str
    title: str | None
    published_at: datetime | None
    text: str
    source_type: DocumentSourceType


@dataclass(frozen=True)
class RawOrganisation:
    """One organisation record of an [`OrganisationSearchAdapter`](#organisationsearchadapter):
    the Crunchbase-mapped fields [Discovery](/architecture/rules.md#discovery) needs for a
    `CRUNCHBASE_SEARCH` candidate."""

    name: str
    domain: str | None
    country_code: str | None
    industry: str | None
    employee_count: int | None


class NewsSearchAdapter(Protocol):
    """A news plug-in's `search` (`API-69`)."""

    async def search(
        self,
        *,
        query: str,
        countries: Collection[str],
        since: datetime,
        until: datetime,
        max_items: int,
    ) -> list[RawNewsItem]: ...


class OrganisationSearchAdapter(Protocol):
    """`CRUNCHBASE`'s `search` (`API-69`), restricted by the ICP."""

    async def search(
        self,
        *,
        country_codes: Collection[str],
        industry_codes: Collection[str],
        employee_min: int | None,
        employee_max: int | None,
        max_results: int,
    ) -> list[RawOrganisation]: ...


#: Registered news-search adapters, by plug-in code; empty until that plug-in's task adds one.
NEWS_SEARCH_ADAPTERS: Mapping[SourcePluginCode, NewsSearchAdapter] = {}

#: Registered organisation-search adapters, by plug-in code; empty until `CRUNCHBASE`'s task
#: adds one.
ORGANISATION_SEARCH_ADAPTERS: Mapping[SourcePluginCode, OrganisationSearchAdapter] = {}
