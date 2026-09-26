"""Contract tests of the CSRF check ([Conventions](/architecture/interfaces.md#conventions)
CSRF, `S-SEC-02`, `AC-53`)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from tests.contract.conftest import _http_client

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_every_state_changing_request_without_x_requested_with_answers_403(
    running_app: FastAPI, method: str
) -> None:
    async with _http_client(running_app) as http:
        response = await http.request(method, "/api/v1/auth/login")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_the_csrf_check_runs_even_on_an_unknown_path(running_app: FastAPI) -> None:
    async with _http_client(running_app) as http:
        response = await http.post("/api/v1/this-path-does-not-exist")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_a_get_request_needs_no_x_requested_with_header(running_app: FastAPI) -> None:
    async with _http_client(running_app) as http:
        response = await http.get("/api/v1/health")

    assert response.status_code != 403
