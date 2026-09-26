"""Builds the api's async database engine from `DATABASE_URL`
([SQLAlchemy and Alembic](/guidelines/python.md#sqlalchemy-and-alembic))."""

from __future__ import annotations

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def build_engine(database_url: str) -> AsyncEngine:
    """Creates the async engine, forcing the `postgresql+psycopg` driver."""
    url = make_url(database_url).set(drivername="postgresql+psycopg")
    return create_async_engine(url)
