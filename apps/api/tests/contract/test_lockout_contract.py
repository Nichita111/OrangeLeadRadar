"""Contract tests of the lockout and disabled-account notes of `API-01`
([Authentication and users](/architecture/interfaces.md#authentication-and-users), G3)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI

from tests.contract.conftest import PASSWORD, _http_client

pytestmark = pytest.mark.contract

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


async def test_the_maximum_th_failure_and_every_attempt_during_the_lock_answer_423(
    running_app: FastAPI, sales_user: tuple[uuid.UUID, str, str]
) -> None:
    _, email, _password = sales_user
    max_failures: int = running_app.state.settings.login_max_failures
    async with _http_client(running_app, headers=HEADERS) as http:
        for _ in range(max_failures - 1):
            response = await http.post(
                "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
            )
            assert response.status_code == 401

        locking_attempt = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
        )
        assert locking_attempt.status_code == 423
        assert locking_attempt.json()["error"]["details"]["retry_after_min"] > 0

        during_the_lock = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert during_the_lock.status_code == 423


async def test_a_disabled_user_gets_403_only_with_the_right_password(
    running_app: FastAPI,
    sales_user: tuple[uuid.UUID, str, str],
    admin_client: httpx.AsyncClient,
) -> None:
    user_id, email, password = sales_user
    disable = await admin_client.patch(f"/api/v1/users/{user_id}", json={"status": "DISABLED"})
    assert disable.status_code == 200

    async with _http_client(running_app, headers=HEADERS) as http:
        wrong_password = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": "the-wrong-password"}
        )
        assert wrong_password.status_code == 401

        right_password = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert right_password.status_code == 403
