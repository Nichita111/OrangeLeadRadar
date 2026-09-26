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
    accounts_and_contacts,
    audit_and_health,
    auth_and_users,
    discovery,
    evaluation,
    feedback_and_alerts,
    industries_and_markets,
    outreach_and_crm,
    prospects_and_evidence,
    runs_and_plugins,
    scoring,
    services_and_questions,
)
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
    app.include_router(audit_and_health.audit_stub_router, prefix=API_PREFIX)
    app.include_router(auth_and_users.router, prefix=API_PREFIX)
    app.include_router(services_and_questions.router, prefix=API_PREFIX)
    app.include_router(scoring.router, prefix=API_PREFIX)
    app.include_router(industries_and_markets.router, prefix=API_PREFIX)
    app.include_router(accounts_and_contacts.router, prefix=API_PREFIX)
    app.include_router(runs_and_plugins.router, prefix=API_PREFIX)
    app.include_router(discovery.router, prefix=API_PREFIX)
    app.include_router(feedback_and_alerts.router, prefix=API_PREFIX)
    app.include_router(outreach_and_crm.router, prefix=API_PREFIX)
    app.include_router(prospects_and_evidence.router, prefix=API_PREFIX)
    app.include_router(evaluation.router, prefix=API_PREFIX)
    return app
