"""The anonymous `{id, name}` object several interface shapes nest, defined once here."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class IdName(BaseModel):
    """The anonymous `{id, name}` shape nested by several responses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
