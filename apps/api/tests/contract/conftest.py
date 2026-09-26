"""Fixtures for the contract tests: the api application, run through its real lifespan against
an `httpx.ASGITransport`, so no socket is opened
([Testing Contract tests](/guidelines/testing.md#contract-tests))."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from leadradar.api.app import create_app
from leadradar.settings import ApiSettings


@pytest.fixture
def app() -> FastAPI:
    settings = ApiSettings(database_url=SecretStr("postgresql://u:p@localhost/db"))
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        # `raise_app_exceptions=False`: Starlette's `ServerErrorMiddleware` re-raises an
        # unhandled exception after sending the response, for the ASGI server's own logging;
        # a raw ASGI transport must not treat that as the request itself failing.
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield http
