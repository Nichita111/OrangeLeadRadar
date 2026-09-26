"""Builds the api's async database engine from `DATABASE_URL`
([SQLAlchemy and Alembic](/guidelines/python.md#sqlalchemy-and-alembic)), and the per-request
session dependency of [api Design](/architecture/services/api.md#design) ("one transaction per
request")."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def psycopg_url(database_url: str) -> URL:
    """`DATABASE_URL` with the `postgresql+psycopg` driver forced."""
    return make_url(database_url).set(drivername="postgresql+psycopg")


def build_engine(database_url: str) -> AsyncEngine:
    """Creates the async engine over `psycopg_url`."""
    return create_async_engine(psycopg_url(database_url))


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One `AsyncSession` on `app.state.engine` per request. The transaction itself is opened by
    the capability function the route calls ([api Design]
    (/architecture/services/api.md#design), "that function owns the transaction")."""
    session_factory = async_sessionmaker(request.app.state.engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
