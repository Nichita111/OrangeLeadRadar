"""Unit tests of the `SERPAPI` `search` adapter (`API-69`; [Source detection]
(/architecture/rules.md#source-detection))."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.http import CrawlHttpClient
from leadradar.plugins.serpapi import SerpapiWebSearch

pytestmark = pytest.mark.unit


def _client(handler: httpx.MockTransport | None, status: int = 200) -> CrawlHttpClient:
    def default(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        return httpx.Response(
            status,
            json={
                "organic_results": [
                    {"link": "https://acme-test.com/careers"},
                    {"link": "https://other.example/careers"},
                ]
            },
        )

    return CrawlHttpClient(
        adapter="SERPAPI",
        user_agent="LeadRadar-test/1.0",
        host_delay_ms=0,
        min_interval_ms=0,
        requests_allowed=None,
        timeout_s=5,
        clock=lambda: datetime(2026, 9, 26, 12, 0, tzinfo=UTC),
        http=httpx.AsyncClient(transport=handler or httpx.MockTransport(default)),
        skip_pacing=True,
    )


async def test_the_search_sends_engine_google_and_the_query_and_returns_links_in_order() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        return httpx.Response(
            200,
            json={
                "organic_results": [
                    {"link": "https://acme-test.com/careers"},
                    {"link": "https://other.example/careers"},
                ]
            },
        )

    client = _client(httpx.MockTransport(handler))

    results = await SerpapiWebSearch(api_key="secret").search('"Acme Corp" careers', client)

    assert results == ["https://acme-test.com/careers", "https://other.example/careers"]
    [search_request] = [r for r in sent if r.url.path != "/robots.txt"]
    query = dict(search_request.url.params)
    assert query["engine"] == "google"
    assert query["q"] == '"Acme Corp" careers'
    assert query["api_key"] == "secret"


async def test_a_5xx_answer_raises_plugin_fetch_failed() -> None:
    client = _client(None, status=503)

    with pytest.raises(PluginFetchFailed):
        await SerpapiWebSearch(api_key="secret").search("query", client)
