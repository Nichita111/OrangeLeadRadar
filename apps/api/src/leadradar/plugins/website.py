"""The `WEBSITE` adapter of the [Source plug-ins](/architecture/services/worker.md#source-plug-ins)
table: HTML over HTTP from the account's `WEBSITE`, `NEWSROOM` and `INVESTOR_RELATIONS` sources
and their same-host links, to link depth 2, up to `CRAWL_MAX_PAGES_PER_SITE` pages per source,
plus up to `CRAWL_MAX_PDFS` of the linked PDF reports. A page or PDF request that answers a
redirect within the account's registrable domain is followed, each hop counted against the same
budget ([Fetch window](/architecture/rules.md#fetch-window) step 3, decision G8 of
`adr-21-source-detection-timing-and-crawler-redirects.md`)."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from leadradar.core.crawl_redirects import redirect_target
from leadradar.core.enums import AccountSourceKind, DocumentSourceType, SourcePluginCode
from leadradar.core.source_detection import LinkCandidate
from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.http import CrawlHttpClient, RobotsDisallowed, fetched_content_type
from leadradar.plugins.shapes import FetchContext, RawItem

logger = logging.getLogger(__name__)

#: [Source detection](/architecture/rules.md#source-detection) Algorithm: an alternate link of
#: either of these types names an RSS or Atom feed.
_FEED_LINK_TYPES = frozenset({"application/rss+xml", "application/atom+xml"})

#: Crawled first `WEBSITE`, then `NEWSROOM`, then `INVESTOR_RELATIONS`
#: ([Fetch window](/architecture/rules.md#fetch-window) step 3, order 9a), so the home page is
#: the crawl's first item and survives `max_items`.
_CRAWL_ORDER = (
    AccountSourceKind.WEBSITE,
    AccountSourceKind.NEWSROOM,
    AccountSourceKind.INVESTOR_RELATIONS,
)
_CRAWL_ORDER_INDEX = {kind: index for index, kind in enumerate(_CRAWL_ORDER)}


def _title_of(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        return title or None
    return None


def home_page_candidates(body: str, base_url: str) -> tuple[list[LinkCandidate], list[str]]:
    """[Source detection](/architecture/rules.md#source-detection) Algorithm's home-page inputs:
    every `<a href>`, resolved against `base_url` and stripped of its fragment, with its visible
    text, in document order; and every `<link rel="alternate">` of type RSS or Atom, resolved."""
    soup = BeautifulSoup(body, "html.parser")
    links = [
        LinkCandidate(
            url=urljoin(base_url, str(anchor["href"])).split("#", 1)[0],
            text=anchor.get_text(" ", strip=True),
        )
        for anchor in soup.find_all("a", href=True)
    ]
    feed_urls = [
        urljoin(base_url, str(tag["href"]))
        for tag in soup.find_all("link", rel=lambda value: bool(value) and "alternate" in value)
        if str(tag.get("type", "")).lower() in _FEED_LINK_TYPES and tag.get("href")
    ]
    return links, feed_urls


@dataclass(frozen=True)
class WebsiteCrawl:
    """`WebsitePlugin.crawl`'s result: the items `fetch` returns, and the account's home page as
    read this job — `(final_url, html)` of the first `ACTIVE` `WEBSITE` source's own page, after
    any redirect, or `None` when it could not be read — for [Source detection]
    (/architecture/rules.md#source-detection)."""

    items: list[RawItem]
    home_page: tuple[str, str] | None


class _Budget:
    """How many more requests one source's page crawl, or the job's PDF crawl, may make; each
    redirect hop spends one, exactly as a page does ([Fetch window]
    (/architecture/rules.md#fetch-window) step 3, decision G10)."""

    def __init__(self, limit: int) -> None:
        self.remaining = limit

    def take(self) -> bool:
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


class WebsitePlugin:
    """`API-68` for `WEBSITE`."""

    def __init__(self, *, max_pages_per_site: int, max_pdfs: int) -> None:
        self._max_pages_per_site = max_pages_per_site
        self._max_pdfs = max_pdfs

    async def _resolve(
        self, client: CrawlHttpClient, url: str, domain: str, seen: set[str], budget: _Budget
    ) -> tuple[str, httpx.Response] | None:
        """Requests `url`, following redirects within `domain`; each hop (the first request
        included) spends one of `budget` and joins `seen`, so a repeated address stops the chain
        (G10). `None` when the request was disallowed, failed, or the budget ran out."""
        current = url
        while True:
            if current in seen or not budget.take():
                return None
            seen.add(current)
            try:
                response = await client.get(current)
            except (RobotsDisallowed, PluginFetchFailed) as error:
                logger.info("WEBSITE request skipped: %s", error)
                return None
            target = redirect_target(
                current, response.status_code, response.headers.get("location"), domain
            )
            if target is None:
                return current, response
            current = target

    async def crawl(self, context: FetchContext, client: CrawlHttpClient) -> WebsiteCrawl:
        items: list[RawItem] = []
        pdf_links: list[str] = []
        seen: set[str] = set()
        home_page: tuple[str, str] | None = None
        domain = context.account.domain

        sources = sorted(
            (source for source in context.sources if source.kind in _CRAWL_ORDER_INDEX),
            key=lambda source: _CRAWL_ORDER_INDEX[source.kind],
        )
        for source in sources:
            pages_budget = _Budget(self._max_pages_per_site)
            host: str | None = None
            queue: deque[tuple[str, int]] = deque([(source.url, 0)])
            while queue and pages_budget.remaining > 0:
                url, depth = queue.popleft()
                if url in seen:
                    continue
                result = await self._resolve(client, url, domain, seen, pages_budget)
                if result is None:
                    continue
                final_url, response = result
                if host is None:
                    host = urlsplit(final_url).hostname
                if not response.is_success or fetched_content_type(response) != "HTML":
                    continue
                text = response.text
                if home_page is None and depth == 0 and source.kind is AccountSourceKind.WEBSITE:
                    home_page = (final_url, text)
                soup = BeautifulSoup(text, "html.parser")
                items.append(
                    RawItem(
                        url=url,
                        title=_title_of(soup),
                        published_at=None,
                        content_type="HTML",
                        body=response.content,
                        source_type=DocumentSourceType.COMPANY_PUBLICATION,
                        plugin_code=SourcePluginCode.WEBSITE,
                    )
                )
                if depth >= 2:
                    continue
                for anchor in soup.find_all("a", href=True):
                    link = urljoin(final_url, str(anchor["href"])).split("#", 1)[0]
                    if link in seen or urlsplit(link).hostname != host:
                        continue
                    if link.lower().endswith(".pdf"):
                        if link not in pdf_links:
                            pdf_links.append(link)
                    else:
                        queue.append((link, depth + 1))

        pdf_budget = _Budget(self._max_pdfs)
        for pdf_url in pdf_links:
            if pdf_url in seen or pdf_budget.remaining <= 0:
                continue
            result = await self._resolve(client, pdf_url, domain, seen, pdf_budget)
            if result is None:
                continue
            final_url, response = result
            if not response.is_success or fetched_content_type(response) != "PDF":
                continue
            items.append(
                RawItem(
                    url=pdf_url,
                    title=None,
                    published_at=None,
                    content_type="PDF",
                    body=response.content,
                    source_type=DocumentSourceType.COMPANY_PUBLICATION,
                    plugin_code=SourcePluginCode.WEBSITE,
                )
            )
        return WebsiteCrawl(items=items[: context.max_items], home_page=home_page)

    async def fetch(self, context: FetchContext, client: CrawlHttpClient) -> list[RawItem]:
        return (await self.crawl(context, client)).items
