"""Contract test of [N-07](/requirements/system.md) and the `AC-67` session-token and password
half: no log line written while signing in, logging out, creating a user or resetting a password
contains the password or the session token."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from fastapi import FastAPI

from leadradar.logs import configure_json_logging
from tests.contract.conftest import PASSWORD, _http_client

pytestmark = pytest.mark.contract

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


async def test_no_log_line_of_sign_in_logout_create_or_reset_contains_the_password_or_the_token(
    running_app: FastAPI,
    sales_user: tuple[uuid.UUID, str, str],
    admin_client: httpx.AsyncClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_json_logging("INFO")
    _, email, password = sales_user
    new_password = "a-reset-password"

    async with _http_client(running_app, headers=HEADERS) as http:
        login = await http.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        session_cookie = login.cookies["leadradar_session"]
        http.headers["Cookie"] = f"leadradar_session={session_cookie}"
        logout = await http.post("/api/v1/auth/logout")
        assert logout.status_code == 204

    created = await admin_client.post(
        "/api/v1/users",
        json={
            "email": f"logged-{uuid.uuid4()}@example.com",
            "display_name": "Logged",
            "role": "SALES",
            "password": PASSWORD,
        },
    )
    assert created.status_code == 200
    user_id = created.json()["id"]

    reset = await admin_client.patch(f"/api/v1/users/{user_id}", json={"password": new_password})
    assert reset.status_code == 200

    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    for line in lines:
        record = json.loads(line)
        dumped = json.dumps(record)
        assert password not in dumped
        assert new_password not in dumped
        assert PASSWORD not in dumped
        assert session_cookie not in dumped
