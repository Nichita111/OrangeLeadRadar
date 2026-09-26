"""Alembic environment for the [SQL store](/architecture/sql-store.md).

Reads no environment itself: the entry point
([`leadradar.api.main`](/architecture/services/api.md#runtime)) builds the `ApiSettings` and
passes it through `config.attributes["settings"]` before running `command.upgrade`. Migrations
run over a synchronous `psycopg` connection even though the api itself is async end to end,
because Alembic's migration context is synchronous.
"""

from __future__ import annotations

import importlib

from sqlalchemy import create_engine, pool

from alembic import context
from leadradar.db.base import Base
from leadradar.db.session import psycopg_url
from leadradar.settings import ApiSettings

# Imported for its side effect: populates Base.metadata with every model.
importlib.import_module("leadradar.db.models")

config = context.config
target_metadata = Base.metadata


def _settings() -> ApiSettings:
    settings = config.attributes.get("settings")
    if settings is None:
        raise RuntimeError(
            "alembic/env.py needs an ApiSettings instance in config.attributes['settings']; "
            "it reads no environment variable itself."
        )
    if not isinstance(settings, ApiSettings):
        raise RuntimeError("config.attributes['settings'] must be an ApiSettings instance.")
    return settings


def run_migrations_online() -> None:
    settings = _settings()
    url = psycopg_url(settings.database_url.get_secret_value())
    config.attributes["embedding_dim"] = settings.embedding_dim
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


run_migrations_online()
