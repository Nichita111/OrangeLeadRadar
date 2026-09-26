"""AC-54 (docs/requirements/acceptance.md):
"Given an Admin, when they create a Sales user, disable them, and try to disable or demote
themselves, then the user exists, the disabled user's sessions stop authenticating, and each
self-change is refused `409`."

Driven through `API-04`/`API-05`/`API-06` (docs/architecture/interfaces.md#authentication-and-
users-contracts): "an Admin cannot change their own role or disable themselves (409 CONFLICT)"
and "Disabling a user revokes their sessions."
"""

from __future__ import annotations

import uuid

import pytest

from conftest import api_get, api_patch, api_post, login

ADMIN_EMAIL = "admin@leadradar.local"


@pytest.mark.ac("AC-54")
def test_admin_creates_disables_a_sales_user_and_cannot_disable_or_demote_themselves(seeded):
    env = seeded["env"]
    _, admin = login(ADMIN_EMAIL, env["SEED_ADMIN_PASSWORD"])
    assert admin is not None
    admin_id = api_get("/auth/me", client=admin).json()["id"]

    victim_email = f"ac54-victim-{uuid.uuid4().hex}@leadradar.local"
    victim_password = "a-long-enough-password-1"
    created = api_post(
        "/users", client=admin,
        json={
            "email": victim_email,
            "display_name": "AC-54 Victim",
            "role": "SALES",
            "password": victim_password,
        },
    )
    assert created.status_code == 200, created.text
    victim_id = created.json()["id"]

    # "the user exists"
    listed = api_get("/users", client=admin)
    assert listed.status_code == 200, listed.text
    assert any(u["id"] == victim_id for u in listed.json()), listed.text

    # The new user's session, established before they are disabled.
    _, victim = login(victim_email, victim_password)
    assert victim is not None
    assert api_get("/auth/me", client=victim).status_code == 200

    # Admin disables them.
    disabled = api_patch(f"/users/{victim_id}", client=admin, json={"status": "DISABLED"})
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["status"] == "DISABLED"

    # "the disabled user's sessions stop authenticating"
    after_disable = api_get("/auth/me", client=victim)
    assert after_disable.status_code == 401, after_disable.text

    # "and try to disable or demote themselves ... each self-change is refused 409"
    self_demote = api_patch(f"/users/{admin_id}", client=admin, json={"role": "SALES"})
    assert self_demote.status_code == 409, self_demote.text

    self_disable = api_patch(f"/users/{admin_id}", client=admin, json={"status": "DISABLED"})
    assert self_disable.status_code == 409, self_disable.text

    # The Admin's own session still authenticates - the self-change was refused, not applied.
    still_admin = api_get("/auth/me", client=admin)
    assert still_admin.status_code == 200, still_admin.text
    assert still_admin.json()["role"] == "ADMIN"
