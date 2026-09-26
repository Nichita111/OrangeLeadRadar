"""The `CAREERS` adapter of the [Source plug-ins](/architecture/services/worker.md#source-plug-ins)
table: the public Greenhouse and Lever postings APIs when a `CAREERS`
[`account_source`](/architecture/sql-store.md#account_source) is on their host; otherwise the
career page's listing is crawled like `WEBSITE` and each posting page fetched."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from leadradar.core.enums import AccountSourceKind, DocumentSourceType, SourcePluginCode
from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.http import CrawlHttpClient, RobotsDisallowed
from leadradar.plugins.shapes import FetchContext, RawItem

logger = logging.getLogger(__name__)


def _json_item(
    *, url: str, title: str | None, published_at: datetime | None, record: object
) -> RawItem:
    return RawItem(
        url=url,
        title=title,
        published_at=published_at,
        content_type="JSON",
        body=json.dumps(record).encode("utf-8"),
        source_type=DocumentSourceType.JOB_POSTING,
        plugin_code=SourcePluginCode.CAREERS,
    )


def _html_of(fragment: str | None) -> str | None:
    if not fragment:
        return None
    return BeautifulSoup(fragment, "html.parser").get_text("\n")


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def _greenhouse(source_url: str, client: CrawlHttpClient) -> list[RawItem]:
    token = urlsplit(source_url).path.strip("/").split("/")[0]
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    response = await client.get(url)
    if not response.is_success:
        return []
    payload = response.json()
    items: list[RawItem] = []
    for job in payload.get("jobs") or []:
        location = (job.get("location") or {}).get("name")
        description = _html_of(job.get("content"))
        items.append(
            _json_item(
                url=job.get("absolute_url") or url,
                title=job.get("title"),
                published_at=_parse_iso(job.get("updated_at")),
                record={"title": job.get("title"), "location": location, "content": description},
            )
        )
    return items


async def _lever(source_url: str, client: CrawlHttpClient) -> list[RawItem]:
    token = urlsplit(source_url).path.strip("/").split("/")[0]
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    response = await client.get(url)
    if not response.is_success:
        return []
    postings = response.json()
    items: list[RawItem] = []
    for posting in postings if isinstance(postings, list) else []:
        created_at_ms = posting.get("createdAt")
        published_at = (
            datetime.fromtimestamp(created_at_ms / 1000, tz=UTC)
            if isinstance(created_at_ms, int | float)
            else None
        )
        location = (posting.get("categories") or {}).get("location")
        description = _html_of(posting.get("description")) or posting.get("descriptionPlain")
        items.append(
            _json_item(
                url=posting.get("hostedUrl") or url,
                title=posting.get("text"),
                published_at=published_at,
                record={"title": posting.get("text"), "location": location, "content": description},
            )
        )
    return items


async def _crawl(source_url: str, client: CrawlHttpClient, max_pages: int) -> list[RawItem]:
    """`otherwise`: the listing is crawled like `WEBSITE`, one depth, and each posting page
    fetched as a `JOB_POSTING`."""
    host = urlsplit(source_url).hostname
    try:
        listing = await client.get(source_url)
    except (RobotsDisallowed, PluginFetchFailed) as error:
        logger.info("CAREERS listing skipped: %s", error)
        return []
    if not listing.is_success:
        return []
    soup = BeautifulSoup(listing.text, "html.parser")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        link = urljoin(source_url, str(anchor["href"])).split("#", 1)[0]
        if urlsplit(link).hostname == host and link != source_url and link not in links:
            links.append(link)

    items: list[RawItem] = []
    for link in links[:max_pages]:
        try:
            response = await client.get(link)
        except (RobotsDisallowed, PluginFetchFailed) as error:
            logger.info("CAREERS posting skipped: %s", error)
            continue
        if not response.is_success:
            continue
        posting_soup = BeautifulSoup(response.text, "html.parser")
        title = (
            posting_soup.title.string.strip()
            if posting_soup.title and posting_soup.title.string
            else None
        )
        items.append(
            RawItem(
                url=link,
                title=title,
                published_at=None,
                content_type="HTML",
                body=response.content,
                source_type=DocumentSourceType.JOB_POSTING,
                plugin_code=SourcePluginCode.CAREERS,
            )
        )
    return items


class CareersPlugin:
    """`API-68` for `CAREERS`."""

    def __init__(self, *, max_pages_per_site: int) -> None:
        self._max_pages_per_site = max_pages_per_site

    async def fetch(self, context: FetchContext, client: CrawlHttpClient) -> list[RawItem]:
        items: list[RawItem] = []
        for source in context.sources:
            if source.kind is not AccountSourceKind.CAREERS:
                continue
            host = (urlsplit(source.url).hostname or "").lower()
            try:
                if host.endswith("greenhouse.io"):
                    items.extend(await _greenhouse(source.url, client))
                elif host.endswith("lever.co"):
                    items.extend(await _lever(source.url, client))
                else:
                    items.extend(await _crawl(source.url, client, self._max_pages_per_site))
            except PluginFetchFailed as error:
                logger.info("CAREERS source skipped: %s", error)

        in_window = [
            item
            for item in items
            if item.published_at is None or context.since <= item.published_at <= context.until
        ]
        return in_window[: context.max_items]
