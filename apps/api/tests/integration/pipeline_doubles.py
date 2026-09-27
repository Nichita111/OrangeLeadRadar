"""Test doubles shared by the integration tests that run a pipeline step through the job loop:
the clock, the session factory, the provider side of the crawl client (`Web`) and the embedder
(`API-67`)."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from leadradar.ai.settings import FixtureMode
from leadradar.plugins.http import CrawlHttpClient

T0 = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
GDELT_SEARCH = "https://api.gdeltproject.org/api/v2/doc/doc"
DIM = 1024


def vec(*head: float) -> list[float]:
    return [*head, *([0.0] * (DIM - len(head)))]


def session_factory(connection: AsyncConnection) -> Callable[[], AsyncSession]:
    def make() -> AsyncSession:
        return AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    return make


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


class Web:
    """The provider side: routes by URL prefix, and every request it received."""

    def __init__(self) -> None:
        self.routes: list[tuple[str, int, str, bytes]] = []
        self.requests: list[httpx.Request] = []

    def add(
        self, prefix: str, content: str | bytes | object, *, status: int = 200, kind: str = "html"
    ) -> None:
        content_type = {
            "html": "text/html",
            "json": "application/json",
            "xml": "text/xml",
            "png": "image/png",
        }[kind]
        body = (
            content
            if isinstance(content, bytes)
            else content.encode()
            if isinstance(content, str)
            else json.dumps(content).encode()
        )
        self.routes.append((prefix, status, content_type, body))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        for prefix, status, content_type, body in self.routes:
            if str(request.url).startswith(prefix):
                return httpx.Response(status, headers={"content-type": content_type}, content=body)
        return httpx.Response(404, text="not found")

    @property
    def pages(self) -> list[httpx.Request]:
        return [request for request in self.requests if request.url.path != "/robots.txt"]

    def searches(self) -> list[dict[str, list[str]]]:
        return [
            parse_qs(urlsplit(str(request.url)).query)
            for request in self.pages
            if str(request.url).startswith(GDELT_SEARCH)
        ]


def html(topic: str, links: Sequence[str] = ()) -> str:
    sentence = f"{topic} announced a new logistics hub this quarter and hired more staff. "
    paragraphs = "".join(f"<p>{sentence}Detail {index} about {topic}.</p>" for index in range(6))
    anchors = "".join(f'<a href="{link}">more</a>' for link in links)
    return (
        f"<html><head><title>{topic}</title></head><body><article><h1>{topic}</h1>"
        f"{paragraphs}{anchors}</article></body></html>"
    )


def gdelt_articles(urls: Sequence[str]) -> dict[str, Any]:
    return {
        "articles": [
            {"url": url, "title": f"Article {index}", "seendate": f"202609{20 - index:02d}T100000Z"}
            for index, url in enumerate(urls)
        ]
    }


def feed(entries: Sequence[tuple[str, str | None]]) -> str:
    items = "".join(
        f"<item><title>{link}</title><link>{link}</link>"
        "<pubDate>Sun, 20 Sep 2026 10:00:00 GMT</pubDate>"
        + (f"<description><![CDATA[{text}]]></description>" if text else "")
        + "</item>"
        for link, text in entries
    )
    return (
        '<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>'
        f"{items}</channel></rss>"
    )


class Embedder:
    """`API-67`: a vector per text from `known`, else the vector of the first of `markers` the
    text contains, else a one-hot vector unique to the text; answers `503` once
    `fail_from_call` calls were made."""

    def __init__(
        self,
        known: dict[str, list[float]] | None = None,
        markers: dict[str, list[float]] | None = None,
    ) -> None:
        self.known = known or {}
        self.markers = markers or {}
        self.calls: list[list[str]] = []
        self.fail_from_call: int | None = None
        self._unique: dict[str, int] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        texts: list[str] = json.loads(request.content)["inputs"]
        if self.fail_from_call is not None and len(self.calls) >= self.fail_from_call:
            return httpx.Response(503)
        self.calls.append(texts)
        vectors = []
        for text in texts:
            marker = next((m for m in self.markers if m in text), None)
            if text not in self.known and marker is not None:
                self.known[text] = self.markers[marker]
            if text not in self.known:
                index = self._unique.setdefault(text, len(self._unique))
                self.known[text] = vec(*([0.0] * (10 + index)), 1.0)
            vectors.append(self.known[text])
        return httpx.Response(200, json=vectors)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))


def install_web(monkeypatch: pytest.MonkeyPatch) -> Web:
    """Puts a `Web` behind the crawl client the `FETCH` step builds."""
    server = Web()

    def build(
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
        return CrawlHttpClient(
            adapter=adapter,
            user_agent=user_agent,
            host_delay_ms=host_delay_ms,
            min_interval_ms=min_interval_ms,
            requests_allowed=requests_allowed,
            timeout_s=timeout_s,
            clock=clock,
            http=httpx.AsyncClient(transport=httpx.MockTransport(server)),
            skip_pacing=True,
        )

    monkeypatch.setattr("leadradar.worker.steps.fetch.build_crawl_client", build)
    return server
