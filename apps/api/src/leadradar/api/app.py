"""Builds the FastAPI application ([api Design](/architecture/services/api.md#design)):
mounts every router under `/api/v1`, serves the OpenAPI document there, and turns off the
interactive docs pages. A lifespan opens the one async database engine and the one
`httpx.AsyncClient` the health checks use, and closes them."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import httpx
from fastapi import FastAPI

from leadradar.api import (
    accounts,
    audit_and_health,
    auth_and_users,
    evaluation,
    feedback_and_alerts,
)
from leadradar.api.constants import API_PREFIX
from leadradar.api.csrf import CsrfMiddleware
from leadradar.api.errors import register_error_handlers
from leadradar.api.request_identity import RequestIdentityMiddleware
from leadradar.clock import build_clock
from leadradar.db.session import build_engine
from leadradar.settings import ApiSettings


def _build_lifespan(
    settings: ApiSettings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.engine = build_engine(settings.database_url.get_secret_value())
        app.state.http_client = httpx.AsyncClient()
        app.state.clock = build_clock(settings)
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
    # CSRF is added first so it ends up inside `RequestIdentityMiddleware` (the outermost
    # middleware, added last): its `403` response still carries `X-Request-Id` and is written to
    # the request log line ([`csrf.py`](csrf.py)).
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(RequestIdentityMiddleware)
    register_error_handlers(app)
    app.include_router(audit_and_health.router, prefix=API_PREFIX)
    app.include_router(evaluation.router, prefix=API_PREFIX)
    app.include_router(feedback_and_alerts.router, prefix=API_PREFIX)
    app.include_router(auth_and_users.build_auth_router(settings), prefix=API_PREFIX)
    app.include_router(auth_and_users.build_users_router(settings), prefix=API_PREFIX)
    app.include_router(accounts.router, prefix=API_PREFIX)
    return app
