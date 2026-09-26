"""Fixtures for the signal contract tests.

These tests need a real PostgreSQL with the schema applied so that the gateway can write
``audit_event`` rows.  Reuses the database container from the integration conftest.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.settings import ApiSettings
from leadradar.db.session import build_engine


@pytest.fixture(scope="session")
def _api_settings_for_signal(database_url: str) -> ApiSettings:
    return ApiSettings(database_url=SecretStr(database_url))


@pytest.fixture
async def async_session(database_url: str) -> AsyncIterator[AsyncSession]:
    """One async session per test, rolled back afterwards."""
    engine = build_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    async with engine.begin() as conn, AsyncSession(bind=conn) as session:  # type: ignore[call-arg]
        sp = await conn.begin_nested()
        try:
            yield session
        finally:
            await sp.rollback()
    await engine.dispose()
