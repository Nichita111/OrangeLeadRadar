"""Per-test fixtures of the integration tests
([Integration tests](/guidelines/testing.md#integration-tests)): the shared container of the
root `conftest.py`, migrated once to head as the owner with the application role granted; each
test gets its own connection, as `leadradar_app`, wrapped in a transaction that is rolled back so
tests stay independent."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import Connection, create_engine
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from leadradar.db.session import build_engine
from leadradar.settings import ApiSettings


@pytest.fixture
def sync_connection(database_url: str) -> Iterator[Connection]:
    """One connection per test, as the application role, in a transaction that is rolled back at
    the end."""
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            yield connection
        finally:
            trans.rollback()
    engine.dispose()


@pytest.fixture
async def async_engine(api_settings: ApiSettings) -> AsyncIterator[AsyncEngine]:
    engine = build_engine(api_settings.database_url.get_secret_value())
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_connection(api_settings: ApiSettings) -> AsyncIterator[AsyncConnection]:
    """One `AsyncConnection` per test, in a transaction rolled back at the end, so a test can
    insert through the existing sync factories with `await connection.run_sync(...)` and read
    through a capability function in the same transaction."""
    engine = build_engine(api_settings.database_url.get_secret_value())
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def async_session(async_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """An `AsyncSession` bound to `async_connection`'s already-open transaction, via a nested
    savepoint, so the capability function's own `session.begin()` never commits the outer
    transaction the fixture rolls back."""
    async with AsyncSession(
        bind=async_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as session:
        yield session


@pytest.fixture
async def db_session(async_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """One `AsyncSession` per test, joined onto an outer transaction through a savepoint: a
    capability function's own `commit()` only releases the savepoint, so the whole test is
    rolled back at the end regardless of how many transactions the code under test committed
    (Risks, `design.md`)."""
    async with async_engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()
