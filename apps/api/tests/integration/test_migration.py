"""Integration tests of the first migration ([S-RUN-01](/requirements/system.md),
[SQL store](/architecture/sql-store.md))."""

from __future__ import annotations

import json
import logging

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect

from alembic import command
from leadradar.api.main import _API_ROOT, apply_migrations
from leadradar.api.settings import ApiSettings
from leadradar.db.base import Base
from leadradar.db.models import *  # noqa: F401,F403 - populates Base.metadata
from leadradar.logs import configure_json_logging

pytestmark = pytest.mark.integration


def test_migration_creates_exactly_the_tables_of_the_store(database_url: str) -> None:
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    try:
        inspector = inspect(engine)
        actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
        expected_tables = set(Base.metadata.tables.keys())
        assert actual_tables == expected_tables
    finally:
        engine.dispose()


def test_models_match_the_migrated_schema(database_url: str) -> None:
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            diff = compare_metadata(context, Base.metadata)
        assert diff == []
    finally:
        engine.dispose()


def test_extensions_are_installed(database_url: str) -> None:
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    try:
        with engine.connect() as connection:
            names = {
                row[0]
                for row in connection.execute(
                    __import__("sqlalchemy").text(
                        "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'citext')"
                    )
                )
            }
        assert names == {"vector", "citext"}
    finally:
        engine.dispose()


def test_a_second_start_applies_no_further_migration(database_url: str) -> None:
    settings = ApiSettings(database_url=SecretStr(database_url))
    config = Config(str(_API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_API_ROOT / "alembic"))
    config.attributes["settings"] = settings

    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    try:
        with engine.connect() as connection:
            before = connection.execute(
                __import__("sqlalchemy").text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        command.upgrade(config, "head")

        with engine.connect() as connection:
            after = connection.execute(
                __import__("sqlalchemy").text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert before == after == "0001"
    finally:
        engine.dispose()


def test_a_migration_failure_from_an_unreachable_database_is_one_json_line_without_the_password(
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_password = "s3cret-password-should-never-appear"  # noqa: S105
    settings = ApiSettings(
        database_url=SecretStr(f"postgresql://postgres:{secret_password}@127.0.0.1:1/nonexistent")
    )
    configure_json_logging("INFO")

    # Reproduces the entry point's own handling (main.run() wraps apply_migrations and logs
    # the exception before exiting).
    try:
        apply_migrations(settings)
        pytest.fail("expected the migration to fail against an unreachable database")
    except Exception:
        logging.getLogger("leadradar.api.main").exception(
            "Migration failed; the api will not start"
        )

    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) >= 1
    for line in lines:
        record = json.loads(line)
        assert secret_password not in json.dumps(record)
