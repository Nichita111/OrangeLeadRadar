"""Builds the api's async database engine from `DATABASE_URL`
([SQLAlchemy and Alembic](/guidelines/python.md#sqlalchemy-and-alembic))."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def build_engine(database_url: str) -> AsyncEngine:
    """Creates the async engine, forcing the `postgresql+psycopg` driver."""
    url = make_url(database_url).set(drivername="postgresql+psycopg")
    return create_async_engine(url)


@asynccontextmanager
async def get_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield one `AsyncSession` bound to `engine`.

    The caller manages the transaction (`async with session.begin()`).
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
