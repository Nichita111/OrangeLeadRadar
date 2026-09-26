"""Unit tests of [Health](/architecture/interfaces.md#health): `derive_health_status` and
`read_health`. No socket is opened: `httpx.MockTransport` stands in for every dependency, and
`pytest-socket` would fail the test if one were."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from leadradar.audit import health as health_module
from leadradar.audit.health import (
    HealthCheckStatus,
    HealthStatus,
    derive_health_status,
    read_health,
)
from leadradar.settings import ApiSettings

pytestmark = pytest.mark.unit


class _FakeEngine:
    """Stands in for the `AsyncEngine` in tests that assert on a check other than `database`:
    calling it raises, and `_bounded` reports that as `DOWN`, same as any other check failure
    (P-10, no fallback result)."""


def _fake_engine() -> AsyncEngine:
    return cast(AsyncEngine, _FakeEngine())


def make_settings(**overrides: Any) -> ApiSettings:
    defaults: dict[str, Any] = {
        "database_url": SecretStr("postgresql://u:p@localhost/db"),
        "migration_database_url": SecretStr("postgresql://u:p@localhost/db"),
    }
    defaults.update(overrides)
    return ApiSettings(**defaults)


# --- derive_health_status -----------------------------------------------------------------


def test_status_is_ok_when_every_check_is_ok() -> None:
    checks = {
        "database": HealthCheckStatus.OK,
        "embedder": HealthCheckStatus.OK,
        "classifier": HealthCheckStatus.OK,
        "llm": HealthCheckStatus.OK,
    }
    assert derive_health_status(checks) == HealthStatus.OK


def test_status_is_degraded_when_only_the_embedder_is_down() -> None:
    checks = {
        "database": HealthCheckStatus.OK,
        "embedder": HealthCheckStatus.DOWN,
        "classifier": HealthCheckStatus.OK,
        "llm": HealthCheckStatus.OK,
    }
    assert derive_health_status(checks) == HealthStatus.DEGRADED


def test_status_is_degraded_when_classifier_and_llm_are_not_configured() -> None:
    checks = {
        "database": HealthCheckStatus.OK,
        "embedder": HealthCheckStatus.OK,
        "classifier": HealthCheckStatus.NOT_CONFIGURED,
        "llm": HealthCheckStatus.NOT_CONFIGURED,
    }
    assert derive_health_status(checks) == HealthStatus.DEGRADED


@pytest.mark.parametrize(
    "others",
    [
        {
            "embedder": HealthCheckStatus.OK,
            "classifier": HealthCheckStatus.OK,
            "llm": HealthCheckStatus.OK,
        },
        {
            "embedder": HealthCheckStatus.DOWN,
            "classifier": HealthCheckStatus.NOT_CONFIGURED,
            "llm": HealthCheckStatus.OK,
        },
    ],
)
def test_status_is_down_whenever_the_database_check_is_not_ok(others: dict[str, Any]) -> None:
    checks = {"database": HealthCheckStatus.DOWN, **others}
    assert derive_health_status(checks) == HealthStatus.DOWN


# --- read_health: bounding and failure handling --------------------------------------------


async def test_a_slow_check_reports_down_within_the_timeout_and_others_still_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def slow_database(engine: object) -> HealthCheckStatus:
        await asyncio.sleep(10)
        return HealthCheckStatus.OK

    monkeypatch.setattr(health_module, "_check_database", slow_database)
    transport = httpx.MockTransport(lambda request: httpx.Response(200))
    settings = make_settings(health_timeout_ms=10)

    async with httpx.AsyncClient(transport=transport) as http:
        result = await read_health(settings, _fake_engine(), http)

    assert result.checks["database"] == HealthCheckStatus.DOWN
    assert result.checks["embedder"] == HealthCheckStatus.OK


async def test_a_raising_check_reports_down_and_does_not_raise_out_of_read_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def raising_embedder(http: httpx.AsyncClient, url: str) -> HealthCheckStatus:
        raise RuntimeError("boom")

    monkeypatch.setattr(health_module, "_check_embedder", raising_embedder)
    transport = httpx.MockTransport(lambda request: httpx.Response(200))
    settings = make_settings()

    async with httpx.AsyncClient(transport=transport) as http:
        result = await read_health(settings, _fake_engine(), http)

    assert result.checks["embedder"] == HealthCheckStatus.DOWN


# --- replay fixture mode ---------------------------------------------------------------------


async def test_replay_reports_ok_for_a_readable_fixture_dir_with_no_network_call(
    tmp_path: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "openrouter" in str(request.url):
            raise AssertionError("no call to OpenRouter is expected in replay")
        return httpx.Response(200)

    settings = make_settings(fixture_mode="replay", fixture_dir=tmp_path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await read_health(settings, _fake_engine(), http)

    assert result.checks["classifier"] == HealthCheckStatus.OK
    assert result.checks["llm"] == HealthCheckStatus.OK


async def test_replay_reports_down_for_a_missing_fixture_dir(tmp_path: Any) -> None:
    settings = make_settings(fixture_mode="replay", fixture_dir=tmp_path / "missing")
    transport = httpx.MockTransport(lambda request: httpx.Response(200))

    async with httpx.AsyncClient(transport=transport) as http:
        result = await read_health(settings, _fake_engine(), http)

    assert result.checks["classifier"] == HealthCheckStatus.DOWN
    assert result.checks["llm"] == HealthCheckStatus.DOWN


# --- OpenRouter-backed checks outside replay -------------------------------------------------


async def test_no_key_reports_not_configured_with_no_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "openrouter" in str(request.url):
            raise AssertionError("no call is expected without a configured key")
        return httpx.Response(200)

    settings = make_settings()  # openrouter_api_key defaults to None
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await read_health(settings, _fake_engine(), http)

    assert result.checks["classifier"] == HealthCheckStatus.NOT_CONFIGURED
    assert result.checks["llm"] == HealthCheckStatus.NOT_CONFIGURED


async def test_with_a_key_calls_the_key_endpoint_with_the_bearer_token_and_reports_ok() -> None:
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "openrouter" in str(request.url):
            captured["path"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            return httpx.Response(200)
        return httpx.Response(200)

    settings = make_settings(openrouter_api_key=SecretStr("sekret-token"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await read_health(settings, _fake_engine(), http)

    assert result.checks["classifier"] == HealthCheckStatus.OK
    assert result.checks["llm"] == HealthCheckStatus.OK
    assert captured["path"] == "https://openrouter.ai/api/v1/key"
    assert captured["auth"] == "Bearer sekret-token"


@pytest.mark.parametrize("status_code", [401, 500])
async def test_with_a_key_a_non_2xx_answer_reports_down(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "openrouter" in str(request.url):
            return httpx.Response(status_code)
        return httpx.Response(200)

    settings = make_settings(openrouter_api_key=SecretStr("sekret-token"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await read_health(settings, _fake_engine(), http)

    assert result.checks["classifier"] == HealthCheckStatus.DOWN
    assert result.checks["llm"] == HealthCheckStatus.DOWN


# --- the embedder check ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "expected"), [(200, HealthCheckStatus.OK), (503, HealthCheckStatus.DOWN)]
)
async def test_embedder_check_reports_from_the_status_code(
    status_code: int, expected: HealthCheckStatus
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    settings = make_settings()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await read_health(settings, _fake_engine(), http)

    assert result.checks["embedder"] == expected


async def test_embedder_check_reports_down_on_a_refused_connection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    settings = make_settings()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await read_health(settings, _fake_engine(), http)

    assert result.checks["embedder"] == HealthCheckStatus.DOWN
