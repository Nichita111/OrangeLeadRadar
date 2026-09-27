"""Contract tests of `API-01` to `API-03` and `API-78` ([Authentication and users](
/architecture/interfaces.md#authentication-and-users), `S-SEC-01`, `S-SEC-02`, `S-SEC-04`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.app import create_app
from leadradar.auth.users import UserCreateData, create_user
from leadradar.core.enums import AppUserRole
from leadradar.db.models.identity import AppUser
from leadradar.seed.demo import DEMO_ADMIN_EMAIL, DEMO_SALES_EMAIL
from leadradar.settings import ApiSettings
from tests.contract.conftest import PASSWORD, _http_client

pytestmark = pytest.mark.contract

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


async def test_login_answers_authenticated_user_and_sets_the_session_cookie(
    running_app: FastAPI, sales_user: tuple[uuid.UUID, str, str]
) -> None:
    user_id, email, password = sales_user
    async with _http_client(running_app, headers=HEADERS) as http:
        response = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )

        assert response.status_code == 200
        body = response.json()
        assert body == {
            "id": str(user_id),
            "email": email,
            "display_name": "Sales",
            "role": "SALES",
        }

        assert response.cookies.get("leadradar_session")
        set_cookie_header = response.headers.get_list("set-cookie")[0]
        assert set_cookie_header.startswith("leadradar_session=")
        assert "HttpOnly" in set_cookie_header
        assert "Secure" in set_cookie_header
        assert "SameSite=Lax" in set_cookie_header
        assert "Path=/api/v1" in set_cookie_header
        assert "Max-Age=" in set_cookie_header


async def test_wrong_email_and_wrong_password_answer_the_same_401_message(
    running_app: FastAPI, sales_user: tuple[uuid.UUID, str, str]
) -> None:
    _, email, _password = sales_user
    async with _http_client(running_app, headers=HEADERS) as http:
        wrong_email = await http.post(
            "/api/v1/auth/login", json={"email": "unknown@example.com", "password": PASSWORD}
        )
        wrong_password = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": "the-wrong-one"}
        )

    assert wrong_email.status_code == wrong_password.status_code == 401
    assert wrong_email.json() == wrong_password.json()
    assert wrong_email.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_an_invalid_login_body_answers_422_without_echoing_the_password(
    running_app: FastAPI,
) -> None:
    secret_password = "s3cret-should-never-be-echoed"
    async with _http_client(running_app, headers=HEADERS) as http:
        # `email` sent as a number: invalid, alongside a password that must never come back.
        response = await http.post(
            "/api/v1/auth/login", json={"email": 12345, "password": secret_password}
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION"
    assert secret_password not in response.text
    fields = body["error"]["details"]["fields"]
    assert any(field["field"] == "email" for field in fields)


async def test_logout_clears_the_cookie_and_the_old_cookie_no_longer_authenticates(
    sales_client: httpx.AsyncClient,
) -> None:
    logout = await sales_client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    set_cookie_header = logout.headers.get_list("set-cookie")[0]
    assert "Max-Age=0" in set_cookie_header

    me = await sales_client.get("/api/v1/auth/me")
    assert me.status_code == 401


async def test_me_answers_the_signed_in_users_role(
    sales_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    sales_me = await sales_client.get("/api/v1/auth/me")
    admin_me = await admin_client.get("/api/v1/auth/me")

    assert sales_me.status_code == 200
    assert sales_me.json()["role"] == "SALES"
    assert admin_me.status_code == 200
    assert admin_me.json()["role"] == "ADMIN"


async def test_me_answers_401_without_a_cookie(running_app: FastAPI) -> None:
    async with _http_client(running_app) as http:
        response = await http.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.fixture
async def replay_app(api_settings: ApiSettings) -> AsyncIterator[FastAPI]:
    app = create_app(api_settings.model_copy(update={"fixture_mode": "replay"}))
    async with app.router.lifespan_context(app):
        yield app


async def _ensure_demo_sales_user(app: FastAPI, api_settings: ApiSettings) -> uuid.UUID:
    """The demo dataset's Sales user, created through the capability when absent; the contract
    database is shared by the session, so an earlier test may have made it already."""
    async with AsyncSession(app.state.engine, expire_on_commit=False) as db:
        existing = (
            await db.execute(select(AppUser.id).where(AppUser.email == DEMO_SALES_EMAIL))
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        user = await create_user(
            db,
            actor_id=None,
            data=UserCreateData(
                email=DEMO_SALES_EMAIL,
                display_name="sales",
                role=AppUserRole.SALES,
                password=PASSWORD,
            ),
            now=datetime.now(tz=UTC),
            password_min_length=api_settings.password_min_length,
        )
        return user.id


async def test_demo_login_answers_404_and_sets_no_cookie_outside_replay(
    running_app: FastAPI,
) -> None:
    async with _http_client(running_app, headers=HEADERS) as http:
        response = await http.post("/api/v1/auth/demo-login", json={"role": "SALES"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert "set-cookie" not in response.headers


async def test_demo_login_in_replay_signs_in_as_the_demo_user_of_the_role(
    replay_app: FastAPI, api_settings: ApiSettings
) -> None:
    user_id = await _ensure_demo_sales_user(replay_app, api_settings)
    async with _http_client(replay_app, headers=HEADERS) as http:
        response = await http.post("/api/v1/auth/demo-login", json={"role": "SALES"})
        # The `Secure` cookie is carried as a header over this plain `http://` transport, as
        # `_signed_in_client` does.
        http.headers["Cookie"] = f"leadradar_session={response.cookies['leadradar_session']}"
        me = await http.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["id"] == str(user_id)
    assert response.json()["role"] == "SALES"
    set_cookie_header = response.headers.get_list("set-cookie")[0]
    assert set_cookie_header.startswith("leadradar_session=")
    assert "HttpOnly" in set_cookie_header
    assert "Path=/api/v1" in set_cookie_header
    assert me.status_code == 200
    assert me.json()["email"] == DEMO_SALES_EMAIL


async def test_demo_login_in_replay_answers_404_when_the_roles_demo_user_does_not_exist(
    replay_app: FastAPI,
) -> None:
    async with AsyncSession(replay_app.state.engine) as db:
        admin_exists = (
            await db.execute(select(AppUser.id).where(AppUser.email == DEMO_ADMIN_EMAIL))
        ).scalar_one_or_none()
    assert admin_exists is None, "the contract database is expected to hold no demo Admin"
    async with _http_client(replay_app, headers=HEADERS) as http:
        response = await http.post("/api/v1/auth/demo-login", json={"role": "ADMIN"})

    assert response.status_code == 404
    assert "set-cookie" not in response.headers
