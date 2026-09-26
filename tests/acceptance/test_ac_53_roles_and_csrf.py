"""AC-53 (docs/requirements/acceptance.md):
"Given every contract of [interfaces](/architecture/interfaces.md) with a path, when it is
called anonymously, as Sales and as Admin, then it answers `401`, `403` or success exactly as
its roles column states, and any `POST` without `X-Requested-With` answers `403`."

Deferred by this task (`.work/auth-and-audit/task.md`) to "every contract other than `API-01` to
`API-06` and `API-61`: those routes do not exist yet; each is checked by the task that builds
it, and in full at the release gate." This test covers exactly that subset: the Authentication
and users contracts (docs/architecture/interfaces.md#authentication-and-users-contracts) and
`/health` (docs/architecture/interfaces.md#audit-and-health-contracts).

Roles column of docs/architecture/interfaces.md#conventions: `-` anonymous, `*` any signed-in
user, `A` Admin only. "Authorisation is enforced by the api on every route; a signed-in user
without the role gets 403 FORBIDDEN" and "every other route except API-61 requires [a session]
and accepts no other credential" (so an anonymous caller of any route but API-01/API-61 gets
401, never reaching a role check).
"""

from __future__ import annotations

import uuid

import pytest
import requests

from conftest import api_get, api_patch, api_post, login

ADMIN_EMAIL = "admin@leadradar.local"
SALES_EMAIL = "sales@leadradar.local"


@pytest.fixture(scope="module")
def clients(seeded):
    env = seeded["env"]
    _, admin = login(ADMIN_EMAIL, env["SEED_ADMIN_PASSWORD"])
    assert admin is not None
    _, sales = login(SALES_EMAIL, env["SEED_SALES_PASSWORD"])
    assert sales is not None
    return {"admin": admin, "sales": sales}


@pytest.mark.ac("AC-53")
def test_auth_route_api_01_is_open_to_anyone(seeded, clients):
    env = seeded["env"]
    body = {"email": ADMIN_EMAIL, "password": env["SEED_ADMIN_PASSWORD"]}

    anonymous = api_post("/auth/login", json=body)
    assert anonymous.status_code == 200, anonymous.text

    as_sales = api_post("/auth/login", client=clients["sales"], json=body)
    assert as_sales.status_code == 200, as_sales.text

    as_admin = api_post("/auth/login", client=clients["admin"], json=body)
    assert as_admin.status_code == 200, as_admin.text


@pytest.mark.ac("AC-53")
def test_health_route_api_61_is_open_to_anyone(seeded, clients):
    base_url = seeded["base_url"]
    anonymous = requests.get(f"{base_url}/health", timeout=10)
    assert anonymous.status_code in (200, 503), anonymous.text

    as_sales = api_get("/health", client=clients["sales"])
    assert as_sales.status_code in (200, 503), as_sales.text

    as_admin = api_get("/health", client=clients["admin"])
    assert as_admin.status_code in (200, 503), as_admin.text


@pytest.mark.ac("AC-53")
def test_any_signed_in_route_api_02_api_03_reject_anonymous_and_allow_sales_and_admin(seeded, clients):
    # API-03 (GET /auth/me): anonymous 401, Sales and Admin succeed.
    anon_me = api_get("/auth/me")
    assert anon_me.status_code == 401, anon_me.text

    sales_me = api_get("/auth/me", client=clients["sales"])
    assert sales_me.status_code == 200, sales_me.text
    assert sales_me.json()["role"] == "SALES"

    admin_me = api_get("/auth/me", client=clients["admin"])
    assert admin_me.status_code == 200, admin_me.text
    assert admin_me.json()["role"] == "ADMIN"

    # API-02 (POST /auth/logout): anonymous 401; a signed-in Sales session may log out. A fresh
    # session is used so the module's shared "sales" client used elsewhere keeps working.
    anon_logout = api_post("/auth/logout")
    assert anon_logout.status_code == 401, anon_logout.text

    env = seeded["env"]
    _, throwaway = login(SALES_EMAIL, env["SEED_SALES_PASSWORD"])
    assert throwaway is not None
    signed_in_logout = api_post("/auth/logout", client=throwaway)
    assert signed_in_logout.status_code == 204, signed_in_logout.text


@pytest.mark.ac("AC-53")
def test_admin_only_routes_api_04_api_05_api_06_reject_anonymous_and_sales_and_allow_admin(
    seeded, clients,
):
    # API-04 (GET /users): anonymous 401, Sales 403, Admin succeeds.
    assert api_get("/users").status_code == 401
    assert api_get("/users", client=clients["sales"]).status_code == 403
    admin_users = api_get("/users", client=clients["admin"])
    assert admin_users.status_code == 200, admin_users.text

    # API-05 (POST /users): anonymous 401, Sales 403, Admin succeeds (a unique email each time).
    def user_body(tag: str) -> dict:
        return {
            "email": f"ac53-{tag}-{uuid.uuid4().hex}@leadradar.local",
            "display_name": f"AC-53 {tag}",
            "role": "SALES",
            "password": "a-long-enough-password-1",
        }

    anon_create = api_post("/users", json=user_body("anon"))
    assert anon_create.status_code == 401, anon_create.text

    sales_create = api_post("/users", client=clients["sales"], json=user_body("sales"))
    assert sales_create.status_code == 403, sales_create.text

    admin_create = api_post("/users", client=clients["admin"], json=user_body("admin"))
    assert admin_create.status_code == 200, admin_create.text
    victim_id = admin_create.json()["id"]

    # API-06 (PATCH /users/{id}): anonymous 401, Sales 403, Admin succeeds.
    random_id = str(uuid.uuid4())
    anon_patch = api_patch(f"/users/{random_id}", json={"display_name": "nope"})
    assert anon_patch.status_code == 401, anon_patch.text

    sales_patch = api_patch(f"/users/{random_id}", client=clients["sales"], json={"display_name": "nope"})
    assert sales_patch.status_code == 403, sales_patch.text

    admin_patch = api_patch(
        f"/users/{victim_id}", client=clients["admin"], json={"display_name": "AC-53 renamed"},
    )
    assert admin_patch.status_code == 200, admin_patch.text
    assert admin_patch.json()["display_name"] == "AC-53 renamed"


@pytest.mark.ac("AC-53")
def test_a_post_without_x_requested_with_answers_403(seeded, clients):
    env = seeded["env"]

    # An anonymous POST to an open route (API-01, role `-`), correct credentials, no header.
    no_header_login = api_post(
        "/auth/login", csrf=False,
        json={"email": ADMIN_EMAIL, "password": env["SEED_ADMIN_PASSWORD"]},
    )
    assert no_header_login.status_code == 403, no_header_login.text

    # A signed-in Admin POST to an Admin-only route (API-05), otherwise a valid request, no
    # header.
    no_header_create = api_post(
        "/users", client=clients["admin"], csrf=False,
        json={
            "email": f"ac53-nocsrf-{uuid.uuid4().hex}@leadradar.local",
            "display_name": "AC-53 no csrf",
            "role": "SALES",
            "password": "a-long-enough-password-1",
        },
    )
    assert no_header_create.status_code == 403, no_header_create.text

    # A signed-in Admin PATCH (API-06), otherwise valid, no header.
    no_header_patch = api_patch(
        f"/users/{str(uuid.uuid4())}", client=clients["admin"], csrf=False,
        json={"display_name": "nope"},
    )
    assert no_header_patch.status_code == 403, no_header_patch.text
