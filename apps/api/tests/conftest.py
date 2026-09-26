"""Shared fixtures ([Python guidelines](/guidelines/python.md#tests)): one
`pgvector/pgvector:pg16` container for the whole test session, with the application role of
[Runtime](/architecture/overview.md#runtime) created by the same init script Compose mounts, and
migrated to head as the owner. Every integration and contract test then runs against
`leadradar_app`, so the tests exercise the same privilege separation as production (G1)."""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy.engine import make_url
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import ExecConfig

from alembic import command
from leadradar.settings import ApiSettings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_API_ROOT = Path(__file__).resolve().parent.parent
_APPLICATION_ROLE_SCRIPT = _REPO_ROOT / "db" / "init" / "01_application_role.sh"
_APPLICATION_ROLE = "leadradar_app"


def _connection_url(container: PostgresContainer, *, username: str, password: str) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(container.port)
    return f"postgresql://{username}:{password}@{host}:{port}/{container.dbname}"


def create_application_role(container: PostgresContainer, app_db_password: str) -> None:
    """Runs [`db/init/01_application_role.sh`](/../../db/init/01_application_role.sh) inside the
    running container: the same file Compose mounts at `/docker-entrypoint-initdb.d/`, not a
    copy (G1)."""
    result = container.exec(
        ExecConfig(
            command=["bash", "-c", _APPLICATION_ROLE_SCRIPT.read_text()],
            environment={
                "POSTGRES_USER": container.username,
                "POSTGRES_DB": container.dbname,
                "APP_DB_PASSWORD": app_db_password,
            },
        )
    )
    assert result.exit_code == 0, result.output.decode()


def migrate_to_head(migration_database_url: str) -> None:
    """Applies every migration as the owner, through `MIGRATION_DATABASE_URL`."""
    settings = ApiSettings(
        database_url=SecretStr(migration_database_url),
        migration_database_url=SecretStr(migration_database_url),
    )
    config = Config(str(_API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_API_ROOT / "alembic"))
    config.attributes["settings"] = settings
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def app_db_password() -> str:
    return secrets.token_urlsafe(16)


@pytest.fixture(scope="session")
def migration_database_url(app_db_password: str) -> Iterator[str]:
    """The owner's connection string of the shared container, migrated to head with the
    application role already created and granted."""
    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as container:
        owner_url = _connection_url(
            container, username=container.username, password=container.password
        )
        create_application_role(container, app_db_password)
        migrate_to_head(owner_url)
        yield owner_url


@pytest.fixture(scope="session")
def database_url(migration_database_url: str, app_db_password: str) -> str:
    """The application role's connection string ([Runtime](
    /architecture/overview.md#runtime)): what `DATABASE_URL` holds in production."""
    url = make_url(migration_database_url).set(username=_APPLICATION_ROLE, password=app_db_password)
    # `str(url)` masks the password with `***` (`URL.__str__` hides it by default); the real
    # password must survive here, or every connection through this fixture would fail with it.
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def api_settings(database_url: str, migration_database_url: str) -> ApiSettings:
    return ApiSettings(
        database_url=SecretStr(database_url),
        migration_database_url=SecretStr(migration_database_url),
    )
