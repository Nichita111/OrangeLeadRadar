"""Unit tests of the crawl client shared by the source plug-ins: crawl etiquette (`N-09`), the
plug-in's rate limit and daily quota ([Plug-in availability]
(/architecture/rules.md#plug-in-availability)) and the fixture adapter of its robots.txt request
([Fixture files](/architecture/overview.md#runtime))."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from leadradar.ai.fixtures import ADAPTER_EXTENSION
from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.http import _PROVIDER_PACES, CrawlHttpClient, RobotsDisallowed

pytestmark = pytest.mark.unit

_AGENT = "LeadRadar-test/1.0"
_ROBOTS_PATH = "/robots.txt"


class FakeTime:
    """A clock that only `sleep` advances, so waits are measured, not slept."""

    def __init__(self) -> None:
        self.now = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
        self.slept: list[float] = []

    def clock(self) -> datetime:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += timedelta(seconds=seconds)


@pytest.fixture(autouse=True)
def _reset_provider_paces() -> None:
    _PROVIDER_PACES.clear()


@pytest.fixture
def fake_time(monkeypatch: pytest.MonkeyPatch) -> FakeTime:
    fake = FakeTime()
    monkeypatch.setattr("leadradar.plugins.http.asyncio.sleep", fake.sleep)
    return fake


class Server:
    """A transport that records what it was sent."""

    def __init__(self, robots: str = "", status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self._robots = robots
        self._status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == _ROBOTS_PATH:
            return httpx.Response(200, text=self._robots)
        return httpx.Response(self._status, text="ok")

    @property
    def pages(self) -> list[httpx.Request]:
        return [request for request in self.requests if request.url.path != _ROBOTS_PATH]


def _client(
    server: Server,
    fake_time: FakeTime,
    *,
    adapter: str | None = None,
    host_delay_ms: int = 1000,
    min_interval_ms: int = 0,
    requests_allowed: int | None = None,
    skip_pacing: bool = False,
) -> CrawlHttpClient:
    return CrawlHttpClient(
        adapter=adapter or f"PLUGIN-{uuid.uuid4().hex}",
        user_agent=_AGENT,
        host_delay_ms=host_delay_ms,
        min_interval_ms=min_interval_ms,
        requests_allowed=requests_allowed,
        timeout_s=5,
        clock=fake_time.clock,
        http=httpx.AsyncClient(transport=httpx.MockTransport(server)),
        skip_pacing=skip_pacing,
    )


async def test_the_robots_request_uses_the_plugin_code_as_its_fixture_adapter(
    fake_time: FakeTime,
) -> None:
    server = Server()
    client = _client(server, fake_time, adapter="WEBSITE")

    await client.get("https://example.com/a")

    assert [request.extensions[ADAPTER_EXTENSION] for request in server.requests] == [
        "WEBSITE",
        "WEBSITE",
    ]


async def test_every_request_carries_the_crawler_user_agent(fake_time: FakeTime) -> None:
    server = Server()
    client = _client(server, fake_time)

    await client.get("https://example.com/a")

    assert {request.headers["user-agent"] for request in server.requests} == {_AGENT}


async def test_a_path_disallowed_by_robots_txt_is_never_sent(fake_time: FakeTime) -> None:
    server = Server(robots="User-agent: *\nDisallow: /private")
    client = _client(server, fake_time)

    with pytest.raises(RobotsDisallowed):
        await client.get("https://example.com/private/page")

    assert server.pages == []
    assert client.requests_made == 1  # robots.txt


@pytest.mark.parametrize("host", ["linkedin.com", "www.linkedin.com"])
async def test_linkedin_is_never_asked(host: str, fake_time: FakeTime) -> None:
    server = Server()
    client = _client(server, fake_time)

    with pytest.raises(RobotsDisallowed):
        await client.get(f"https://{host}/company/x")

    assert server.requests == []


async def test_consecutive_requests_to_one_host_are_the_host_delay_apart(
    fake_time: FakeTime,
) -> None:
    client = _client(Server(), fake_time, host_delay_ms=1000)

    await client.get("https://example.com/a")
    await client.get("https://example.com/b")

    assert fake_time.slept == [1.0, 1.0]  # after robots.txt, and between the two pages


async def test_replay_skips_every_wait(fake_time: FakeTime) -> None:
    client = _client(
        Server(), fake_time, host_delay_ms=1000, min_interval_ms=1000, skip_pacing=True
    )

    await client.get("https://example.com/a")
    await client.get("https://example.com/b")

    assert fake_time.slept == []


async def test_a_plugin_is_spaced_by_its_rate_limit_across_hosts_and_clients(
    fake_time: FakeTime,
) -> None:
    adapter = f"PLUGIN-{uuid.uuid4().hex}"  # 30 requests a minute: 2000 ms apart
    first = _client(Server(), fake_time, adapter=adapter, host_delay_ms=0, min_interval_ms=2000)
    second = _client(Server(), fake_time, adapter=adapter, host_delay_ms=0, min_interval_ms=2000)

    await first.get("https://a.example.com/x")
    await first.get("https://b.example.com/x")
    await second.get("https://c.example.com/x")

    assert (
        fake_time.slept == [2.0] * 5
    )  # robots.txt of three hosts and their three pages, six requests


async def test_the_request_after_the_remaining_daily_quota_is_refused_unsent_and_uncounted(
    fake_time: FakeTime,
) -> None:
    server = Server()
    client = _client(server, fake_time, requests_allowed=2, host_delay_ms=0)

    await client.get("https://example.com/a")  # robots.txt and the page: two requests
    with pytest.raises(PluginFetchFailed, match="daily quota reached"):
        await client.get("https://example.com/b")

    assert len(server.pages) == 1
    assert client.requests_made == 2


async def test_the_robots_request_is_counted_paced_and_refused_after_the_quota(
    fake_time: FakeTime,
) -> None:
    server = Server()
    client = _client(server, fake_time, requests_allowed=0, host_delay_ms=1000)

    with pytest.raises(PluginFetchFailed, match="daily quota reached"):
        await client.get("https://example.com/a")

    assert server.requests == []
    assert client.requests_made == 0


async def test_the_page_waits_the_host_delay_after_the_robots_request(
    fake_time: FakeTime,
) -> None:
    server = Server()
    client = _client(server, fake_time, host_delay_ms=1000)

    await client.get("https://example.com/a")

    assert fake_time.slept == [1.0]
    assert client.requests_made == 2


async def test_a_failed_request_is_counted_and_remembered(fake_time: FakeTime) -> None:
    client = _client(Server(status=503), fake_time, host_delay_ms=0)

    with pytest.raises(PluginFetchFailed):
        await client.get("https://example.com/a")

    assert client.requests_made == 2  # robots.txt and the page
    assert client.succeeded is False
    assert client.last_failure is not None
    assert "503" in client.last_failure


async def test_a_successful_request_is_remembered(fake_time: FakeTime) -> None:
    client = _client(Server(), fake_time)

    await client.get("https://example.com/a")

    assert client.succeeded is True
    assert client.last_failure is None
