"""The `RSS` adapter of the [Source plug-ins](/architecture/services/worker.md#source-plug-ins)
table: parses each `RSS_FEED` [`account_source`](/architecture/sql-store.md#account_source),
fetching an item's link as HTML when the entry carries no full text. Never reads a feed on
`news.google.com`, whose terms allow personal use only
([ADR-19](/architecture/adrs/adr-19-source-provider-terms-and-limits.md))."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import feedparser

from leadradar.core.account_identity import InvalidDomain, normalise_domain
from leadradar.core.enums import AccountSourceKind, DocumentSourceType, SourcePluginCode
from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.http import CrawlHttpClient, RobotsDisallowed
from leadradar.plugins.shapes import FetchContext, RawItem

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_HOST = "news.google.com"


def _entry_published_at(entry: object) -> datetime | None:
    value = getattr(entry, "get", lambda *_: None)("published")
    if not isinstance(value, str):
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _entry_text(entry: object) -> str | None:
    get = getattr(entry, "get", lambda *_: None)
    content = get("content")
    if isinstance(content, list) and content and isinstance(content[0].get("value"), str):
        return str(content[0]["value"])
    summary = get("summary")
    return summary if isinstance(summary, str) else None


class RssPlugin:
    """`API-68` for `RSS`."""

    async def fetch(self, context: FetchContext, client: CrawlHttpClient) -> list[RawItem]:
        items: list[RawItem] = []
        for source in context.sources:
            if source.kind is not AccountSourceKind.RSS_FEED:
                continue
            if urlsplit(source.url).hostname == _GOOGLE_NEWS_HOST:
                continue
            try:
                own_domain = normalise_domain(source.url) == normalise_domain(
                    context.account.domain
                )
            except InvalidDomain:
                own_domain = False
            source_type = (
                DocumentSourceType.COMPANY_PUBLICATION if own_domain else DocumentSourceType.NEWS
            )
            try:
                response = await client.get(source.url)
            except (RobotsDisallowed, PluginFetchFailed) as error:
                logger.info("RSS feed skipped: %s", error)
                continue
            if not response.is_success:
                continue
            parsed = feedparser.parse(response.content)
            for entry in parsed.entries:
                link = entry.get("link")
                if not isinstance(link, str):
                    continue
                published_at = _entry_published_at(entry)
                if published_at is not None and not (
                    context.since <= published_at <= context.until
                ):
                    continue
                title = entry.get("title") if isinstance(entry.get("title"), str) else None
                text = _entry_text(entry)
                if text:
                    items.append(
                        RawItem(
                            url=link,
                            title=title,
                            published_at=published_at,
                            content_type="HTML",
                            body=text.encode("utf-8"),
                            source_type=source_type,
                            plugin_code=SourcePluginCode.RSS,
                        )
                    )
                    continue
                try:
                    page = await client.get(link)
                except (RobotsDisallowed, PluginFetchFailed) as error:
                    logger.info("RSS item skipped: %s", error)
                    continue
                if not page.is_success:
                    continue
                items.append(
                    RawItem(
                        url=link,
                        title=title,
                        published_at=published_at,
                        content_type="HTML",
                        body=page.content,
                        source_type=source_type,
                        plugin_code=SourcePluginCode.RSS,
                    )
                )
        items.sort(key=lambda item: item.published_at or context.since, reverse=True)
        return items[: context.max_items]
