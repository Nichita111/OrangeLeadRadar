"""HTTP routing errors follow the API's error envelope."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.contract


async def test_unsupported_method_has_an_envelope_and_keeps_allow_header(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/auth/login")

    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
    assert response.json() == {
        "error": {"code": "METHOD_NOT_ALLOWED", "message": "Method Not Allowed"}
    }
