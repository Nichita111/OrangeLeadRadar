"""Builds the api's async database engine from `DATABASE_URL`
([SQLAlchemy and Alembic](/guidelines/python.md#sqlalchemy-and-alembic))."""

from __future__ import annotations

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def psycopg_url(database_url: str) -> URL:
    """`DATABASE_URL` with the `postgresql+psycopg` driver forced."""
    return make_url(database_url).set(drivername="postgresql+psycopg")


def build_engine(database_url: str) -> AsyncEngine:
    """Creates the async engine over `psycopg_url`."""
    return create_async_engine(psycopg_url(database_url))
