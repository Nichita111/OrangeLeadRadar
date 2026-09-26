"""Shapes every interface family reuses: the one generic `Page<T>` of
[Conventions](/architecture/interfaces.md#conventions), and the anonymous `{id, name}` object
several shapes nest (`Run.account`, `ProspectRow.account`'s identity fields, `AlertView.account`,
and similarly named nested objects) — defined once here instead of once per family."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Page[T](BaseModel):
    """`Page<T>` of [Conventions](/architecture/interfaces.md#conventions)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[T]
    page: int
    page_size: int
    total: int


class IdName(BaseModel):
    """The anonymous `{id, name}` shape nested by several responses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
