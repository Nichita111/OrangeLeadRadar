"""`Page<T>` of [Conventions](/architecture/interfaces.md#conventions) Pagination: `page` from 1,
`page_size` defaulting to `PAGE_SIZE_DEFAULT` and at most `PAGE_SIZE_MAX`, answered as
`{items, page, page_size, total}`. Every paged route uses these."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict


class Page[ItemT](BaseModel):
    """`Page<T>`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ItemT]
    page: int
    page_size: int
    total: int


class PageRequest(BaseModel):
    """The `page` and `page_size` a paged request resolved to."""

    model_config = ConfigDict(frozen=True)

    page: int
    page_size: int


def page_request(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int | None, Query(ge=1)] = None,
) -> PageRequest:
    """Dependency: resolves `page_size` against the runtime's `PAGE_SIZE_DEFAULT` and refuses
    one above `PAGE_SIZE_MAX` as a `VALIDATION` error naming `page_size`."""
    settings = request.app.state.settings
    if page_size is None:
        return PageRequest(page=page, page_size=settings.page_size_default)
    if page_size > settings.page_size_max:
        raise RequestValidationError(
            [
                {
                    "loc": ("query", "page_size"),
                    "msg": f"Input should be less than or equal to {settings.page_size_max}",
                    "type": "less_than_equal",
                }
            ]
        )
    return PageRequest(page=page, page_size=page_size)
