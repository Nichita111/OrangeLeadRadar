"""Contract tests of `API-01` to `API-03` ([Authentication and users](
/architecture/interfaces.md#authentication-and-users), `S-SEC-01`, `S-SEC-02`)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI

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
