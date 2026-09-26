"""The [Health](/architecture/interfaces.md#health) shape (`API-61`).

`derive_health_status` is pure; `read_health` is the only I/O, one lightweight call per
dependency bounded by `HEALTH_TIMEOUT_MS`. A check that times out or raises reports `DOWN`;
nothing raises out of `read_health` (P-10, no fallback result, only a reported failure).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from leadradar.api.settings import ApiSettings


class HealthCheckStatus(StrEnum):
    """One dependency's check outcome, of the [Health](/architecture/interfaces.md#health) shape."""

    OK = "OK"
    DOWN = "DOWN"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class HealthStatus(StrEnum):
    """The overall `status` of the [Health](/architecture/interfaces.md#health) shape."""

    OK = "OK"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


@dataclass(frozen=True)
class HealthResult:
    """The answer to `API-61`."""

    status: HealthStatus
    checks: Mapping[str, HealthCheckStatus]


def derive_health_status(checks: Mapping[str, HealthCheckStatus]) -> HealthStatus:
    """`DOWN` when `database` is not `OK`, `DEGRADED` when any other check is not `OK`, else
    `OK`."""
    if checks["database"] != HealthCheckStatus.OK:
        return HealthStatus.DOWN
    if any(value != HealthCheckStatus.OK for key, value in checks.items() if key != "database"):
        return HealthStatus.DEGRADED
    return HealthStatus.OK


async def _bounded(coro: Awaitable[HealthCheckStatus], timeout_s: float) -> HealthCheckStatus:
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except Exception:
        return HealthCheckStatus.DOWN


async def _check_database(engine: AsyncEngine) -> HealthCheckStatus:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return HealthCheckStatus.OK


async def _check_embedder(http: httpx.AsyncClient, embedder_url: str) -> HealthCheckStatus:
    response = await http.get(f"{embedder_url}/health")
    return HealthCheckStatus.OK if response.is_success else HealthCheckStatus.DOWN


def _fixture_dir_readable(fixture_dir: Path) -> HealthCheckStatus:
    readable = fixture_dir.is_dir() and os.access(fixture_dir, os.R_OK)
    return HealthCheckStatus.OK if readable else HealthCheckStatus.DOWN


async def _check_openrouter(http: httpx.AsyncClient, settings: ApiSettings) -> HealthCheckStatus:
    if settings.fixture_mode == "replay":
        return _fixture_dir_readable(settings.fixture_dir)
    if settings.openrouter_api_key is None:
        return HealthCheckStatus.NOT_CONFIGURED
    response = await http.get(
        f"{settings.openrouter_base_url}/key",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}"},
    )
    return HealthCheckStatus.OK if response.is_success else HealthCheckStatus.DOWN


async def read_health(
    settings: ApiSettings, engine: AsyncEngine, http: httpx.AsyncClient
) -> HealthResult:
    """Runs the four checks of [Health](/architecture/interfaces.md#health) concurrently."""
    timeout_s = settings.health_timeout_ms / 1000
    database, embedder, classifier, llm = await asyncio.gather(
        _bounded(_check_database(engine), timeout_s),
        _bounded(_check_embedder(http, settings.embedder_url), timeout_s),
        _bounded(_check_openrouter(http, settings), timeout_s),
        _bounded(_check_openrouter(http, settings), timeout_s),
    )
    checks: dict[str, HealthCheckStatus] = {
        "database": database,
        "embedder": embedder,
        "classifier": classifier,
        "llm": llm,
    }
    return HealthResult(status=derive_health_status(checks), checks=checks)
