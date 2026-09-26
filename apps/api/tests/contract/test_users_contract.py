"""Contract tests of `API-04` to `API-06` ([Authentication and users](
/architecture/interfaces.md#authentication-and-users), `S-SEC-03`, `AC-54`)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI

from tests.contract.conftest import PASSWORD, _http_client

pytestmark = pytest.mark.contract

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


async def test_users_list_has_exactly_the_user_fields_and_no_password_hash(
    admin_client: httpx.AsyncClient, sales_user: tuple[uuid.UUID, str, str]
) -> None:
    response = await admin_client.get("/api/v1/users")

    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 1
    for user in users:
        assert set(user.keys()) == {
            "id",
            "email",
            "display_name",
            "role",
            "status",
            "last_login_at",
        }


async def test_users_list_is_forbidden_to_sales(sales_client: httpx.AsyncClient) -> None:
    response = await sales_client.get("/api/v1/users")
    assert response.status_code == 403


async def test_create_user_answers_200_and_the_new_user(admin_client: httpx.AsyncClient) -> None:
    email = f"new-{uuid.uuid4()}@example.com"
    response = await admin_client.post(
        "/api/v1/users",
        json={
            "email": email,
            "display_name": "A New User",
            "role": "SALES",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email
    assert body["role"] == "SALES"
    assert "password" not in body
    assert "password_hash" not in body


async def test_create_user_refuses_a_password_shorter_than_the_minimum_and_accepts_the_minimum(
    admin_client: httpx.AsyncClient,
) -> None:
    short = await admin_client.post(
        "/api/v1/users",
        json={
            "email": f"short-{uuid.uuid4()}@example.com",
            "display_name": "Short",
            "role": "SALES",
            "password": "eleven-chr",
        },
    )
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "VALIDATION"

    at_minimum = await admin_client.post(
        "/api/v1/users",
        json={
            "email": f"min-{uuid.uuid4()}@example.com",
            "display_name": "At minimum",
            "role": "SALES",
            "password": "twelve-chars",
        },
    )
    assert at_minimum.status_code == 200


async def test_create_user_with_a_taken_email_answers_409_conflict_with_entity_id(
    admin_client: httpx.AsyncClient, sales_user: tuple[uuid.UUID, str, str]
) -> None:
    user_id, email, _password = sales_user
    response = await admin_client.post(
        "/api/v1/users",
        json={
            "email": email.upper(),
            "display_name": "Duplicate",
            "role": "SALES",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["details"]["entity_id"] == str(user_id)


async def test_patch_changes_role_disables_and_reenables_another_user(
    admin_client: httpx.AsyncClient, sales_user: tuple[uuid.UUID, str, str]
) -> None:
    user_id, _email, _password = sales_user

    promoted = await admin_client.patch(f"/api/v1/users/{user_id}", json={"role": "ADMIN"})
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "ADMIN"

    disabled = await admin_client.patch(f"/api/v1/users/{user_id}", json={"status": "DISABLED"})
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"

    reenabled = await admin_client.patch(f"/api/v1/users/{user_id}", json={"status": "ACTIVE"})
    assert reenabled.status_code == 200
    assert reenabled.json()["status"] == "ACTIVE"


async def test_patch_resets_the_password_with_the_minimum_length(
    admin_client: httpx.AsyncClient,
    sales_user: tuple[uuid.UUID, str, str],
    running_app: FastAPI,
) -> None:
    user_id, email, _password = sales_user
    new_password = "a-new-twelve"

    response = await admin_client.patch(f"/api/v1/users/{user_id}", json={"password": new_password})
    assert response.status_code == 200

    async with _http_client(running_app, headers=HEADERS) as http:
        login = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": new_password}
        )
    assert login.status_code == 200


async def test_an_admin_demoting_or_disabling_themselves_answers_409(
    admin_client: httpx.AsyncClient, admin_user: tuple[uuid.UUID, str, str]
) -> None:
    admin_id, _email, _password = admin_user

    demote = await admin_client.patch(f"/api/v1/users/{admin_id}", json={"role": "SALES"})
    assert demote.status_code == 409

    disable = await admin_client.patch(f"/api/v1/users/{admin_id}", json={"status": "DISABLED"})
    assert disable.status_code == 409


async def test_patch_with_an_unknown_field_answers_422_and_an_unknown_id_answers_404(
    admin_client: httpx.AsyncClient, sales_user: tuple[uuid.UUID, str, str]
) -> None:
    user_id, _email, _password = sales_user

    unknown_field = await admin_client.patch(
        f"/api/v1/users/{user_id}", json={"email": "new@example.com"}
    )
    assert unknown_field.status_code == 422

    unknown_id = await admin_client.patch(
        f"/api/v1/users/{uuid.uuid4()}", json={"display_name": "Whoever"}
    )
    assert unknown_id.status_code == 404


async def test_disabling_a_user_stops_their_session_from_authenticating(
    admin_client: httpx.AsyncClient, sales_client: httpx.AsyncClient
) -> None:
    me = await sales_client.get("/api/v1/auth/me")
    sales_id = me.json()["id"]

    disabled = await admin_client.patch(f"/api/v1/users/{sales_id}", json={"status": "DISABLED"})
    assert disabled.status_code == 200

    still_using_old_session = await sales_client.get("/api/v1/auth/me")
    assert still_using_old_session.status_code == 401
