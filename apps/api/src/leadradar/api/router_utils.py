"""One helper every family router uses: an `APIRouter` that carries
[`contract_not_built`](not_built.py) so every route in it answers `501 NOT_IMPLEMENTED` before
authentication and before its input is validated. The `ErrorEnvelope` model is declared once, as
the app's `default` response ([Conventions](/architecture/interfaces.md#conventions);
[api Design](/architecture/services/api.md#design))."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from leadradar.api.not_built import contract_not_built


def stub_router(tag: str) -> APIRouter:
    """An `APIRouter` for one interface family, every route of it a declared stub."""
    return APIRouter(tags=[tag], dependencies=[Depends(contract_not_built)])
