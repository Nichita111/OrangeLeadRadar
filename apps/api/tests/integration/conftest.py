"""Fixtures shared by the integration tests
([Integration tests](/guidelines/testing.md#integration-tests)): one `pgvector/pgvector:pg16`
container for the session, migrated once to head; each test gets its own connection wrapped in
a transaction that is rolled back, so tests stay independent."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import Connection, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.community.postgres import PostgresContainer

from alembic import command
from leadradar.api.settings import ApiSettings
from leadradar.db.session import build_engine

_ALEMBIC_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def _plain_url(container: PostgresContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(container.port)
    return (
        f"postgresql://{container.username}:{container.password}@{host}:{port}/{container.dbname}"
    )


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as container:
        url = _plain_url(container)
        settings = ApiSettings(database_url=SecretStr(url))
        config = Config(str(_ALEMBIC_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(_ALEMBIC_ROOT / "alembic"))
        config.attributes["settings"] = settings
        command.upgrade(config, "head")
        yield url


@pytest.fixture(scope="session")
def api_settings(database_url: str) -> ApiSettings:
    return ApiSettings(database_url=SecretStr(database_url))


@pytest.fixture
def sync_connection(database_url: str) -> Iterator[Connection]:
    """One connection per test, in a transaction that is rolled back at the end."""
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            yield connection
        finally:
            trans.rollback()
    engine.dispose()


@pytest.fixture
async def async_engine(api_settings: ApiSettings) -> AsyncEngine:
    engine = build_engine(api_settings.database_url.get_secret_value())
    yield engine
    await engine.dispose()
