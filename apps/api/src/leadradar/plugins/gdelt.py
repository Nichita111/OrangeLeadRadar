"""The `GDELT` adapter of the [Source plug-ins](/architecture/services/worker.md#source-plug-ins)
table: GDELT DOC 2.0 `mode=ArtList`, JSON, one query per active service from [Fetch
window](/architecture/rules.md#fetch-window), each listed article then fetched as HTML because
GDELT returns metadata only
([ADR-19](/architecture/adrs/adr-19-source-provider-terms-and-limits.md)). Every document it
finds is credited to the GDELT Project, whose terms require it."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlencode

from leadradar.core.crawl_pacing import seconds_to_wait
from leadradar.core.enums import DocumentSourceType, SourcePluginCode
from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.http import CrawlHttpClient, RobotsDisallowed, fetched_content_type
from leadradar.plugins.shapes import FetchContext, RawItem

logger = logging.getLogger(__name__)

_DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_TIMEFORMAT = "%Y%m%d%H%M%S"


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


class GdeltPlugin:
    """`API-68` for `GDELT`. `min_interval_s` and `backoff_s` pace and back off the DOC 2.0 API
    call itself, on top of the client's own per-host pacing of the article fetches that follow."""

    def __init__(self, *, max_records: int, min_interval_s: float, backoff_s: int) -> None:
        self._max_records = max_records
        self._min_interval_s = min_interval_s
        self._backoff_s = backoff_s
        self._last_query_at: datetime | None = None

    async def _search_query(
        self, client: CrawlHttpClient, query: str, since: datetime, until: datetime
    ) -> object:
        if not client.skip_pacing:
            wait = seconds_to_wait(
                last_request_at=self._last_query_at,
                now=client.now(),
                delay_ms=int(self._min_interval_s * 1000),
            )
            if wait > 0:
                await asyncio.sleep(wait)
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(self._max_records),
            "startdatetime": since.strftime(_TIMEFORMAT),
            "enddatetime": until.strftime(_TIMEFORMAT),
        }
        url = f"{_DOC_API_URL}?{urlencode(params)}"
        try:
            response = await client.get(url)
        except PluginFetchFailed:
            self._last_query_at = client.now()
            if not client.skip_pacing:
                await asyncio.sleep(self._backoff_s)
            response = await client.get(url)
        self._last_query_at = client.now()
        try:
            return response.json()
        except ValueError as error:
            raise PluginFetchFailed(f"GDELT answered non-JSON for {query!r}") from error

    async def _collect(
        self,
        client: CrawlHttpClient,
        queries: Sequence[str],
        *,
        since: datetime,
        until: datetime,
        max_items: int,
    ) -> list[RawItem]:
        """Every query's articles, newest first, capped at `max_items`, each fetched as HTML:
        shared by [`fetch`](#fetch) (`API-68`) and [`search`](#search) (`API-69`, no
        `sourcecountry` filter for discovery, G5)."""
        seen_urls: set[str] = set()
        articles: list[tuple[str, str | None, datetime | None]] = []
        for query in queries:
            payload = await self._search_query(client, query, since, until)
            for article in (payload.get("articles") or []) if isinstance(payload, dict) else []:
                url = article.get("url")
                if not isinstance(url, str) or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = article.get("title") if isinstance(article.get("title"), str) else None
                articles.append((url, title, _parse_published_at(article.get("seendate"))))

        items: list[RawItem] = []
        for url, title, published_at in sorted(
            articles, key=lambda entry: entry[2] or since, reverse=True
        )[:max_items]:
            try:
                response = await client.get(url)
            except (RobotsDisallowed, PluginFetchFailed) as error:
                logger.info("GDELT article skipped: %s", error)
                continue
            content_type = fetched_content_type(response)
            if not response.is_success or content_type is None:
                continue
            items.append(
                RawItem(
                    url=url,
                    title=title,
                    published_at=published_at,
                    content_type=content_type,
                    body=response.content,
                    source_type=DocumentSourceType.NEWS,
                    plugin_code=SourcePluginCode.GDELT,
                )
            )
        return items

    async def fetch(self, context: FetchContext, client: CrawlHttpClient) -> list[RawItem]:
        return await self._collect(
            client,
            context.queries or [context.account.name],
            since=context.since,
            until=context.until,
            max_items=context.max_items,
        )

    async def search(
        self,
        query: str,
        *,
        since: datetime,
        until: datetime,
        max_items: int,
        client: CrawlHttpClient,
    ) -> list[RawItem]:
        """`API-69` for `GDELT`: [Discovery](/architecture/rules.md#discovery) step 2's own
        search, over one query and window, with no `sourcecountry` filter (G5: no ISO-to-GDELT
        code table exists)."""
        return await self._collect(client, [query], since=since, until=until, max_items=max_items)
