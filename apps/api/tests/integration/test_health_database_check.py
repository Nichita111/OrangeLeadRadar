"""Integration test of the database check of [Health](/architecture/interfaces.md#health)
(`API-61`) against a real database."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from leadradar.audit.health import HealthCheckStatus, read_health
from leadradar.settings import ApiSettings

pytestmark = pytest.mark.integration


async def test_the_database_check_reports_ok_against_the_test_database(
    api_settings: ApiSettings, async_engine: AsyncEngine
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200))
    ) as http:
        result = await read_health(api_settings, async_engine, http)

    assert result.checks["database"] == HealthCheckStatus.OK
