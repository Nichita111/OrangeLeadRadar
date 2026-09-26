"""Small helpers shared by the models of [db/models](/guidelines/python.md#package-layout),
so that an enum column or a foreign key is declared the same way everywhere."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import MappedColumn, mapped_column


def pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """A PostgreSQL native enum column type, named `<table>_<column>`, whose values are the
    enum's own values (never a Python member name)."""
    return SAEnum(enum_cls, name=name, values_callable=lambda members: [m.value for m in members])


def fk_uuid(
    target: str, *, ondelete: str = "RESTRICT", nullable: bool = False, unique: bool = False
) -> MappedColumn[Any]:
    """A `uuid` foreign key column, `ON DELETE RESTRICT` unless stated otherwise."""
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        unique=unique,
    )
