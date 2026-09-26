"""Fixtures for the signal integration tests: one async session on the shared database
container, rolled back after each test."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.db.session import build_engine


@pytest.fixture
async def async_session(database_url: str) -> AsyncIterator[AsyncSession]:
    """One async session per test, rolled back afterwards."""
    engine = build_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()
