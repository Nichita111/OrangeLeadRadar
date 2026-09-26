"""Contract test guarding [Conventions](/architecture/interfaces.md#conventions) Roles against
every mounted route (`S-SEC-02`, `AC-53`): parses every contracts table of `interfaces.md` and
checks each mounted route answers `401`/`403` exactly as its roles column states. A mounted
route this file cannot find in any contracts table fails, so the matrix grows with every later
task instead of staying hand-listed."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from tests.contract.conftest import _http_client

pytestmark = pytest.mark.contract

_DOCS_ROOT = Path(__file__).resolve().parents[4] / "docs"
_INTERFACES = _DOCS_ROOT / "architecture" / "interfaces.md"
_PARAM_PATTERN = re.compile(r"\{[^}]+\}")
_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def _normalised_path(path: str) -> str:
    return _PARAM_PATTERN.sub("{}", path)


def _contract_roles() -> dict[tuple[str, str], str]:
    """Maps `(method, normalised path)` to its roles column, over every `### … contracts`
    table. A column that narrows the role for some cases (`API-36`: "`*`; `A` for …") maps to
    its leading symbol, the role of the route itself."""
    text = _INTERFACES.read_text()
    roles: dict[tuple[str, str], str] = {}
    for match in re.finditer(
        r"^\|\s*`API-\d+`\s*\|\s*(GET|POST|PATCH|PUT|DELETE)\s*\|\s*`([^`]+)`\s*\|\s*`([-*A])`[^|]*\|",
        text,
        re.MULTILINE,
    ):
        method, path, role = match.groups()
        roles[(method, _normalised_path(path))] = role
    return roles


def _mounted_routes(app: FastAPI) -> list[tuple[str, str, str]]:
    """`(method, path, normalised path)` of every route this task mounts under `/api/v1`, read
    from the served OpenAPI document rather than FastAPI's internal routing objects."""
    routes: list[tuple[str, str, str]] = []
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith("/api/v1"):
            continue
        api_path = path.removeprefix("/api/v1")
        for method in operations:
            if method.upper() == "HEAD" or path.endswith("/openapi.json"):
                continue
            routes.append((method.upper(), path, _normalised_path(api_path)))
    return routes


async def _request(
    running_app: FastAPI, method: str, path: str, cookie_header: str | None
) -> httpx.Response:
    concrete_path = _PARAM_PATTERN.sub(str(uuid.uuid4()), path)
    headers = dict(_HEADERS)
    if cookie_header is not None:
        headers["Cookie"] = cookie_header
    async with _http_client(running_app, headers=headers) as http:
        return await http.request(method, concrete_path, json={})


async def _login_cookie(running_app: FastAPI, email: str, password: str) -> str:
    """A fresh session for one check: `POST /auth/logout` is itself in the matrix, and reusing
    one session across every route would have that check revoke it before later routes are
    tried."""
    async with _http_client(running_app, headers=_HEADERS) as http:
        response = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200, response.text
        return f"leadradar_session={response.cookies['leadradar_session']}"


async def test_every_mounted_route_answers_401_or_403_as_its_roles_column_states(
    running_app: FastAPI,
    sales_user: tuple[uuid.UUID, str, str],
    admin_user: tuple[uuid.UUID, str, str],
) -> None:
    contract_roles = _contract_roles()
    mounted = _mounted_routes(running_app)
    assert mounted, "expected at least one mounted route under /api/v1"

    _, sales_email, sales_password = sales_user
    _, admin_email, admin_password = admin_user

    failures: list[str] = []
    for method, full_path, normalised in mounted:
        key = (method, normalised)
        if key not in contract_roles:
            failures.append(f"{method} {full_path}: not found in any interfaces.md contracts table")
            continue
        roles = contract_roles[key]

        anonymous = await _request(running_app, method, full_path, cookie_header=None)
        if roles in {"*", "A"} and anonymous.status_code != 401:
            failures.append(
                f"{method} {full_path} (roles={roles}): anonymous got "
                f"{anonymous.status_code}, expected 401"
            )
        if roles == "-" and anonymous.status_code in {401, 403}:
            failures.append(
                f"{method} {full_path} (roles={roles}): anonymous got "
                f"{anonymous.status_code}, expected neither 401 nor 403"
            )

        sales_cookie = await _login_cookie(running_app, sales_email, sales_password)
        sales = await _request(running_app, method, full_path, cookie_header=sales_cookie)
        if roles == "A" and sales.status_code != 403:
            failures.append(
                f"{method} {full_path} (roles={roles}): Sales got {sales.status_code}, expected 403"
            )
        if roles in {"*", "-"} and sales.status_code in {401, 403}:
            failures.append(
                f"{method} {full_path} (roles={roles}): Sales got "
                f"{sales.status_code}, expected neither 401 nor 403"
            )

        admin_cookie = await _login_cookie(running_app, admin_email, admin_password)
        admin = await _request(running_app, method, full_path, cookie_header=admin_cookie)
        if roles in {"*", "A", "-"} and admin.status_code in {401, 403}:
            failures.append(
                f"{method} {full_path} (roles={roles}): Admin got "
                f"{admin.status_code}, expected neither 401 nor 403"
            )

    assert not failures, "\n".join(failures)
