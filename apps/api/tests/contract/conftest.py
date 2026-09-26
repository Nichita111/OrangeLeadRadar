"""Fixtures for the contract tests: the api application, run through its real lifespan against
an `httpx.ASGITransport` over the shared migrated container of the root `conftest.py`, so no
socket is opened but every route's own database access is real
([Testing Contract tests](/guidelines/testing.md#contract-tests)). `sales_client` and
`admin_client` are signed in as a Sales user and an Admin created directly through the
`auth.users` capability."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.app import create_app
from leadradar.auth.users import UserCreateData, create_user
from leadradar.core.enums import AppUserRole
from leadradar.settings import ApiSettings

PASSWORD = "a-strong-enough-password"


@pytest.fixture
def app(api_settings: ApiSettings) -> FastAPI:
    return create_app(api_settings)


@pytest.fixture
async def running_app(app: FastAPI) -> AsyncIterator[FastAPI]:
    async with app.router.lifespan_context(app):
        yield app


def _http_client(app: FastAPI, *, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    # `raise_app_exceptions=False`: Starlette's `ServerErrorMiddleware` re-raises an unhandled
    # exception after sending the response, for the ASGI server's own logging; a raw ASGI
    # transport must not treat that as the request itself failing.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver", headers=headers)


@pytest.fixture
async def client(running_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with _http_client(running_app) as http:
        yield http


@pytest.fixture
async def user_factory(
    running_app: FastAPI, api_settings: ApiSettings
) -> Callable[[AppUserRole], Awaitable[tuple[uuid.UUID, str, str]]]:
    """Creates a user directly through the capability (never the routes under test), with a
    random email so tests never collide, and returns its id, email and plain password."""

    async def make(role: AppUserRole) -> tuple[uuid.UUID, str, str]:
        email = f"{role.value.lower()}-{uuid.uuid4()}@example.com"
        async with AsyncSession(running_app.state.engine, expire_on_commit=False) as db:
            user = await create_user(
                db,
                actor_id=None,
                data=UserCreateData(
                    email=email, display_name=role.value.title(), role=role, password=PASSWORD
                ),
                now=datetime.now(tz=UTC),
                password_min_length=api_settings.password_min_length,
            )
        return user.id, email, PASSWORD

    return make


@pytest.fixture
async def sales_user(
    user_factory: Callable[[AppUserRole], Awaitable[tuple[uuid.UUID, str, str]]],
) -> tuple[uuid.UUID, str, str]:
    return await user_factory(AppUserRole.SALES)


@pytest.fixture
async def admin_user(
    user_factory: Callable[[AppUserRole], Awaitable[tuple[uuid.UUID, str, str]]],
) -> tuple[uuid.UUID, str, str]:
    return await user_factory(AppUserRole.ADMIN)


async def _signed_in_client(
    running_app: FastAPI, user: tuple[uuid.UUID, str, str]
) -> AsyncIterator[httpx.AsyncClient]:
    _, email, password = user
    async with _http_client(running_app, headers={"X-Requested-With": "XMLHttpRequest"}) as http:
        response = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200, response.text
        # A `Secure` cookie is never resent by `http.cookiejar` (which httpx's client jar uses)
        # over the plain `http://` transport of this test; carrying it as a header explicitly is
        # what a real browser on `https://` would do automatically (Risks, `design.md`).
        http.headers["Cookie"] = f"leadradar_session={response.cookies['leadradar_session']}"
        yield http


@pytest.fixture
async def sales_client(
    running_app: FastAPI, sales_user: tuple[uuid.UUID, str, str]
) -> AsyncIterator[httpx.AsyncClient]:
    async for http in _signed_in_client(running_app, sales_user):
        yield http


@pytest.fixture
async def admin_client(
    running_app: FastAPI, admin_user: tuple[uuid.UUID, str, str]
) -> AsyncIterator[httpx.AsyncClient]:
    async for http in _signed_in_client(running_app, admin_user):
        yield http
