"""Crawl etiquette (`N-09`, [Fetch window](/architecture/rules.md#fetch-window)) shared by every
[source plug-in](/architecture/services/worker.md#source-plug-ins): one `httpx` client per
`FETCH` job, sent through the record/replay transport
([ADR-11](/architecture/adrs/adr-11-recorded-fixtures.md)), that identifies itself with
`CRAWLER_USER_AGENT`, checks `robots.txt` once per host, paces requests
`CRAWL_HOST_DELAY_MS` apart (and a plug-in's requests `60000 / rate_limit_per_minute` ms
apart), stops at the plug-in's remaining daily quota, counts every request it makes for
[`plugin_usage`](/architecture/sql-store.md#plugin_usage), and never asks `linkedin.com`
([ADR-19](/architecture/adrs/adr-19-source-provider-terms-and-limits.md))."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from leadradar.ai.fixtures import ADAPTER_EXTENSION, build_fixture_client
from leadradar.ai.settings import FixtureMode
from leadradar.core.crawl_pacing import seconds_to_wait
from leadradar.core.document_normalisation import ContentType
from leadradar.plugins.errors import PluginFetchFailed

_LINKEDIN_HOST = "linkedin.com"
_HTML_MEDIA_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_UNTYPED_MEDIA_TYPES = frozenset({"", "application/octet-stream"})


@dataclass
class _ProviderPace:
    """When a plug-in last sent a request, shared by every client of the plug-in in this
    process, so its `rate_limit_per_minute` holds across the jobs of one worker."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_request_at: datetime | None = None


_PROVIDER_PACES: dict[str, _ProviderPace] = {}


class RobotsDisallowed(Exception):
    """`robots.txt` disallows the path; the caller skips it, it is not a failed request."""

    def __init__(self, url: str) -> None:
        super().__init__(f"robots.txt disallows {url}")


def fetched_content_type(response: httpx.Response) -> ContentType | None:
    """What a fetched page is by its `Content-Type`, or by its URL when the header names no type:
    `HTML`, `PDF`, or `None` for anything else - an image, a script - which is not an item
    [Document normalisation](/architecture/rules.md#document-normalisation) takes, so the
    plug-in skips it."""
    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type in _UNTYPED_MEDIA_TYPES:
        return "PDF" if response.url.path.lower().endswith(".pdf") else "HTML"
    if media_type in _HTML_MEDIA_TYPES:
        return "HTML"
    if media_type == "application/pdf":
        return "PDF"
    return None


def _is_linkedin(host: str) -> bool:
    return host == _LINKEDIN_HOST or host.endswith(f".{_LINKEDIN_HOST}")


class CrawlHttpClient:
    """One client for one `FETCH` job's requests to its provider: paced, robots-checked, counted
    in `requests_made` for [`plugin_usage`](/architecture/sql-store.md#plugin_usage). Built fresh
    per job (the worker has no per-process client to share across jobs), and closed by the job
    handler through `aclose`."""

    def __init__(
        self,
        *,
        adapter: str,
        user_agent: str,
        host_delay_ms: int,
        min_interval_ms: int,
        requests_allowed: int | None,
        timeout_s: float,
        clock: Callable[[], datetime],
        http: httpx.AsyncClient,
        skip_pacing: bool = False,
    ) -> None:
        self._adapter = adapter
        self._user_agent = user_agent
        self._host_delay_ms = host_delay_ms
        #: `60000 / rate_limit_per_minute`, between any two requests of the plug-in.
        self._min_interval_ms = min_interval_ms
        #: What is left of the plug-in's `daily_quota` today; `None` without a quota.
        self._requests_allowed = requests_allowed
        self._provider_pace = _PROVIDER_PACES.setdefault(adapter, _ProviderPace())
        self._timeout_s = timeout_s
        self._clock = clock
        self._http = http
        #: `replay` fixture mode answers from committed files with no live host to be polite to
        #: ([ADR-11](/architecture/adrs/adr-11-recorded-fixtures.md)): pacing waits are skipped so
        #: the demo and the acceptance suite stay fast, while `off` and `record` (a live host, be
        #: it the network or a test fixture server) wait as documented.
        self._skip_pacing = skip_pacing
        self._last_request_at: dict[str, datetime] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self.requests_made = 0
        #: For the `FETCH` handler: whether any request got an answer, and why the last failed.
        self.succeeded = False
        self.last_failure: str | None = None

    async def aclose(self) -> None:
        await self._http.aclose()

    @property
    def skip_pacing(self) -> bool:
        return self._skip_pacing

    def now(self) -> datetime:
        return self._clock()

    async def _pace(self, host: str) -> None:
        """Waits the larger of the host's and the plug-in's remaining delay, then records the
        request time for both; the plug-in's lock keeps concurrent jobs in line."""
        async with self._provider_pace.lock:
            if not self._skip_pacing:
                now = self._clock()
                wait = max(
                    seconds_to_wait(
                        last_request_at=self._last_request_at.get(host),
                        now=now,
                        delay_ms=self._host_delay_ms,
                    ),
                    seconds_to_wait(
                        last_request_at=self._provider_pace.last_request_at,
                        now=now,
                        delay_ms=self._min_interval_ms,
                    ),
                )
                if wait > 0:
                    await asyncio.sleep(wait)
            self._last_request_at[host] = self._clock()
            self._provider_pace.last_request_at = self._clock()

    async def _send(self, url: str, host: str) -> httpx.Response:
        """One request of the plug-in, `robots.txt` included: quota-checked, paced, counted."""
        if self._requests_allowed is not None and self.requests_made >= self._requests_allowed:
            self.last_failure = "daily quota reached"
            raise PluginFetchFailed(self.last_failure)
        await self._pace(host)
        self.requests_made += 1
        return await self._http.get(
            url,
            headers={"User-Agent": self._user_agent},
            timeout=self._timeout_s,
            extensions={ADAPTER_EXTENSION: self._adapter},
        )

    async def _robots_allows(self, url: str, host: str, scheme: str, netloc: str) -> bool:
        parser = self._robots.get(host)
        if parser is None:
            parser = RobotFileParser()
            try:
                response = await self._send(f"{scheme}://{netloc}/robots.txt", host)
            except httpx.TransportError:
                parser.parse([])  # unreachable robots.txt: nothing is disallowed by it
            else:
                parser.parse(response.text.splitlines() if response.is_success else [])
            self._robots[host] = parser
        return parser.can_fetch(self._user_agent, url)

    async def get(self, url: str) -> httpx.Response:
        """One paced, robots-checked, counted `GET`. Raises `RobotsDisallowed`, or
        `PluginFetchFailed` on a transport error, `429` or `5xx`; a `4xx` other than `429` is
        returned for the caller to skip."""
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if _is_linkedin(host):
            raise RobotsDisallowed(url)
        if not await self._robots_allows(url, host, parts.scheme, parts.netloc):
            raise RobotsDisallowed(url)
        try:
            response = await self._send(url, host)
        except httpx.TransportError as error:
            self.last_failure = f"{url}: {error}"
            raise PluginFetchFailed(self.last_failure) from error
        if response.status_code == 429 or response.status_code >= 500:
            self.last_failure = f"{url} answered {response.status_code}"
            raise PluginFetchFailed(self.last_failure)
        self.succeeded = True
        return response


def build_crawl_client(
    *,
    adapter: str,
    user_agent: str,
    host_delay_ms: int,
    min_interval_ms: int,
    requests_allowed: int | None,
    timeout_s: float,
    clock: Callable[[], datetime],
    fixture_mode: FixtureMode,
    fixture_dir: Path,
) -> CrawlHttpClient:
    """A [`CrawlHttpClient`](#crawlhttpclient) over the fixture-aware transport
    ([ADR-11](/architecture/adrs/adr-11-recorded-fixtures.md)), one per `FETCH` job."""
    return CrawlHttpClient(
        adapter=adapter,
        user_agent=user_agent,
        host_delay_ms=host_delay_ms,
        min_interval_ms=min_interval_ms,
        requests_allowed=requests_allowed,
        timeout_s=timeout_s,
        clock=clock,
        http=build_fixture_client(fixture_mode, fixture_dir),
        skip_pacing=fixture_mode == "replay",
    )
