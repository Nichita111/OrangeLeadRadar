"""The declarative base every SQLAlchemy model of the [SQL store](/architecture/sql-store.md)
shares, with the naming convention that makes constraint names deterministic and the three
columns every table has: `id`, `created_at` and `updated_at`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base with the store's naming convention. `str` maps to `text`, the
    [SQL store](/architecture/sql-store.md)'s column type, never a length-bounded `varchar`."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {str: Text, datetime: DateTime(timezone=True)}


class TimestampedBase(Base):
    """Adds the `id`, `created_at` and `updated_at` columns every table of the store has."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
