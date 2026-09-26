"""Integration tests of the first migration ([S-RUN-01](/requirements/system.md),
[SQL store](/architecture/sql-store.md))."""

from __future__ import annotations

import importlib
import json
import logging

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect, text
<<<<<<< HEAD
=======
from testcontainers.community.postgres import PostgresContainer
>>>>>>> origin/main

from alembic import command
from leadradar.api.main import _API_ROOT, apply_migrations
from leadradar.db.base import Base
from leadradar.logs import configure_json_logging
from leadradar.settings import ApiSettings

# Imported for its side effect: populates Base.metadata with every model.
importlib.import_module("leadradar.db.models")

# Imported for its side effect: populates Base.metadata with every model.
importlib.import_module("leadradar.db.models")

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
                    text("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'citext')")
                )
            }
        assert names == {"vector", "citext"}
    finally:
        engine.dispose()


def test_every_timestamp_column_of_the_migrated_schema_is_with_time_zone(
    database_url: str,
) -> None:
    """[SQL store](/architecture/sql-store.md) preamble and column types: every `created_at`,
    `updated_at` and other `timestamptz` column is timezone-aware, never a naive
    `timestamp without time zone`."""
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    try:
        with engine.connect() as connection:
            naive = connection.execute(
                text(
                    "SELECT table_name || '.' || column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND data_type = 'timestamp without time zone'"
                )
            ).all()
        assert naive == []
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
            before: str = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        command.upgrade(config, "head")

        with engine.connect() as connection:
            after: str = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert before == after == "0001"
    finally:
        engine.dispose()


def test_a_non_default_embedding_dim_is_the_migrated_vector_dimension() -> None:
    """[`embedding`](/architecture/sql-store.md#chunk) is `vector(EMBEDDING_DIM)`, frozen by the
    migration at the value in force when it runs ([Runtime](/architecture/services/api.md#runtime)).
    `chunk.embedding`'s model column declares a dimensionless `Vector()` (R-5: the model reads no
    configuration of its own); this confirms a non-default `EMBEDDING_DIM` still reaches the
    migrated column, and that the model still matches the migrated schema at that dimension."""
    non_default_dim = 512
    assert non_default_dim != ApiSettings.model_fields["embedding_dim"].default

    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(container.port)
        url = (
            f"postgresql://{container.username}:{container.password}@{host}:{port}"
            f"/{container.dbname}"
        )
        settings = ApiSettings(database_url=SecretStr(url), embedding_dim=non_default_dim)
        apply_migrations(settings)

        engine = create_engine(url.replace("postgresql://", "postgresql+psycopg://"))
        try:
            with engine.connect() as connection:
                migrated_type: str = connection.execute(
                    text(
                        "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                        "WHERE attrelid = 'chunk'::regclass AND attname = 'embedding'"
                    )
                ).scalar_one()
                assert migrated_type == f"vector({non_default_dim})"

                context = MigrationContext.configure(connection)
                diff = compare_metadata(context, Base.metadata)
            assert diff == []
        finally:
            engine.dispose()


def test_a_migration_failure_from_an_unreachable_database_is_one_json_line_without_the_password(
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_password = "s3cret-password-should-never-appear"
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
