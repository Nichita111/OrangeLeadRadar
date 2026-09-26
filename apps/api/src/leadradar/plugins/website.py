"""The `WEBSITE` adapter of the [Source plug-ins](/architecture/services/worker.md#source-plug-ins)
table: HTML over HTTP from the account's `WEBSITE`, `NEWSROOM` and `INVESTOR_RELATIONS` sources
and their same-host links, to link depth 2, up to `CRAWL_MAX_PAGES_PER_SITE` pages per source,
plus up to `CRAWL_MAX_PDFS` of the linked PDF reports."""

from __future__ import annotations

import logging
from collections import deque
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from leadradar.core.enums import AccountSourceKind, DocumentSourceType, SourcePluginCode
from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.http import CrawlHttpClient, RobotsDisallowed
from leadradar.plugins.shapes import FetchContext, RawItem

logger = logging.getLogger(__name__)

_WEBSITE_SOURCE_KINDS = frozenset(
    {
        AccountSourceKind.WEBSITE,
        AccountSourceKind.NEWSROOM,
        AccountSourceKind.INVESTOR_RELATIONS,
    }
)


def _title_of(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        return title or None
    return None


class WebsitePlugin:
    """`API-68` for `WEBSITE`."""

    def __init__(self, *, max_pages_per_site: int, max_pdfs: int) -> None:
        self._max_pages_per_site = max_pages_per_site
        self._max_pdfs = max_pdfs

    async def fetch(self, context: FetchContext, client: CrawlHttpClient) -> list[RawItem]:
        items: list[RawItem] = []
        pdf_links: list[str] = []
        seen: set[str] = set()

        for source in context.sources:
            if source.kind not in _WEBSITE_SOURCE_KINDS:
                continue
            host = urlsplit(source.url).hostname
            queue: deque[tuple[str, int]] = deque([(source.url, 0)])
            pages = 0
            while queue and pages < self._max_pages_per_site:
                url, depth = queue.popleft()
                if url in seen:
                    continue
                seen.add(url)
                try:
                    response = await client.get(url)
                except (RobotsDisallowed, PluginFetchFailed) as error:
                    logger.info("WEBSITE page skipped: %s", error)
                    continue
                if not response.is_success:
                    continue
                pages += 1
                soup = BeautifulSoup(response.text, "html.parser")
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
                    link = urljoin(url, str(anchor["href"])).split("#", 1)[0]
                    if link in seen or urlsplit(link).hostname != host:
                        continue
                    if link.lower().endswith(".pdf"):
                        if link not in pdf_links:
                            pdf_links.append(link)
                    else:
                        queue.append((link, depth + 1))

        for pdf_url in pdf_links[: self._max_pdfs]:
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            try:
                response = await client.get(pdf_url)
            except (RobotsDisallowed, PluginFetchFailed) as error:
                logger.info("WEBSITE PDF skipped: %s", error)
                continue
            if not response.is_success:
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
        return items[: context.max_items]
