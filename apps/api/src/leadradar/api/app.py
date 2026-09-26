"""Builds the FastAPI application ([api Design](/architecture/services/api.md#design)):
mounts every router under `/api/v1`, serves the OpenAPI document there, and turns off the
interactive docs pages. A lifespan opens the one async database engine and the one
`httpx.AsyncClient` the health checks use, and closes them."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import httpx
from fastapi import FastAPI

from leadradar.api import audit_and_health
from leadradar.api.errors import register_error_handlers
from leadradar.api.request_identity import RequestIdentityMiddleware
from leadradar.db.session import build_engine
from leadradar.settings import ApiSettings

API_PREFIX = "/api/v1"


def _build_lifespan(
    settings: ApiSettings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.engine = build_engine(settings.database_url.get_secret_value())
        app.state.http_client = httpx.AsyncClient()
        try:
            yield
        finally:
            await app.state.http_client.aclose()
            await app.state.engine.dispose()

    return lifespan


def create_app(settings: ApiSettings) -> FastAPI:
    """Builds the api application for the given settings."""
    app = FastAPI(
        title="LeadRadar API",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=None,
        redoc_url=None,
        lifespan=_build_lifespan(settings),
    )
    app.add_middleware(RequestIdentityMiddleware)
    register_error_handlers(app)
    app.include_router(audit_and_health.router, prefix=API_PREFIX)
    return app
