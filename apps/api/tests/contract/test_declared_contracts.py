"""[api Design](/architecture/services/api.md#design) "Declared contracts": every REST contract
of [interfaces](/architecture/interfaces.md) is a route from the start, answering
`501 NOT_IMPLEMENTED` until its feature is built
([Conventions](/architecture/interfaces.md#conventions))."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from .interfaces_parsing import ContractRow, rest_contracts

pytestmark = pytest.mark.contract

SAMPLE_ID = "00000000-0000-0000-0000-000000000000"
# `CsrfMiddleware` (`api/csrf.py`) refuses a state-changing request without this header before
# routing sees it; every stub request below must carry it to reach `contract_not_built`.
_CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}
_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _headers(row: ContractRow) -> dict[str, str]:
    return _CSRF_HEADERS if row.method in _STATE_CHANGING_METHODS else {}


def _fill_path(row: ContractRow) -> str:
    """Replaces every `{param}` of a contract's path with a sample UUID."""
    path = row.path
    while "{" in path:
        start = path.index("{")
        end = path.index("}", start)
        path = path[:start] + SAMPLE_ID + path[end + 1 :]
    return path


REST_CONTRACTS = rest_contracts()
# `API-61` (`GET /health`), `API-46`/`API-47` (feedback) and `API-77` (impact) are built by now;
# every other row is still a declared stub.
_BUILT_CONTRACTS = {"API-61", "API-46", "API-47", "API-77"}
STUB_CONTRACTS = [row for row in REST_CONTRACTS if row.id not in _BUILT_CONTRACTS]


def _has_json_body(row: ContractRow) -> bool:
    """A row whose request side is a named shape, not `—` (no request) or a multipart upload."""
    left = row.request_response.split("→", 1)[0].strip()
    return bool(left) and not left.startswith(("—", "multipart"))


def test_every_rest_contract_of_interfaces_is_a_route_with_its_method_and_path(
    app: FastAPI,
) -> None:
    schema = app.openapi()
    declared = {
        (method.upper(), path)
        for path, methods in schema["paths"].items()
        for method in methods
        if method in {"get", "post", "put", "patch", "delete"}
    }
    expected = {(row.method, f"/api/v1{row.path}") for row in REST_CONTRACTS}
    assert expected <= declared, f"missing routes: {expected - declared}"
    assert declared == expected, f"undeclared extra routes: {declared - expected}"


@pytest.mark.parametrize("row", STUB_CONTRACTS, ids=lambda row: row.id)
async def test_a_declared_contract_not_built_answers_501_not_implemented(
    row: ContractRow, client: httpx.AsyncClient
) -> None:
    url = f"/api/v1{_fill_path(row)}"
    response = await client.request(row.method, url, headers=_headers(row))

    assert response.status_code == 501, f"{row.id} {row.method} {url}: {response.text}"
    assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"
    assert "x-request-id" in response.headers


@pytest.mark.parametrize(
    "row",
    [row for row in STUB_CONTRACTS if row.method in {"POST", "PUT", "PATCH"}],
    ids=lambda row: row.id,
)
async def test_a_stub_answers_501_even_when_its_body_misses_required_fields(
    row: ContractRow, client: httpx.AsyncClient
) -> None:
    url = f"/api/v1{_fill_path(row)}"
    response = await client.request(row.method, url, json={}, headers=_headers(row))

    assert response.status_code == 501, f"{row.id} {row.method} {url}: {response.text}"
    assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"


@pytest.mark.parametrize(
    "row",
    [
        row
        for row in STUB_CONTRACTS
        if row.method in {"POST", "PUT", "PATCH"} and _has_json_body(row)
    ],
    ids=lambda row: row.id,
)
async def test_a_malformed_json_body_answers_422_with_the_validation_envelope(
    row: ContractRow, client: httpx.AsyncClient
) -> None:
    url = f"/api/v1{_fill_path(row)}"
    response = await client.request(
        row.method,
        url,
        content=b"not json",
        headers={"content-type": "application/json", **_headers(row)},
    )

    assert response.status_code == 422, f"{row.id} {row.method} {url}: {response.text}"
    assert response.json()["error"]["code"] == "VALIDATION"
