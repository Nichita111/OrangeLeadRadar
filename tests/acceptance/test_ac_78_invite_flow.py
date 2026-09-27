"""AC-78 (docs/requirements/acceptance.md):
"Given an Admin, when they invite `new.sales@leadradar.local` as Sales, then `API-79` returns
the invite with a link under `APP_BASE_URL` carrying the token after `#`, the database holds
only the token's hash, and an `INVITE_CREATED` row names the role; with that token `API-81`
returns the email, role, inviter and expiry, and `API-82` with a display name and a password of
`PASSWORD_MIN_LENGTH` characters answers as `API-01` would, sets the session cookie, creates an
active Sales user and writes `USER_CREATED` with the invite id and `LOGIN_SUCCEEDED`. A Sales
user calling `API-79` is refused `403`."

Driven through `API-79`/`API-81`/`API-82`/`API-04` (`/users`)/`API-60` (`/audit`)
(docs/architecture/interfaces.md#authentication-and-users-contracts,
docs/architecture/interfaces.md#audit-and-health-contracts) of a fresh module stack
(tests/acceptance/docker/compose.override.invites.yml). The invited address is made unique per
run (`ac78-<uuid>@leadradar.local`) so the test is repeatable; the criterion's own
`new.sales@leadradar.local` is illustrative input, not an asserted value.

`APP_BASE_URL` (`http://localhost:8080`) and `PASSWORD_MIN_LENGTH` (`12`) are the defaults of
docs/architecture/services/api.md#runtime; the invites stack changes neither.
"""

from __future__ import annotations

import uuid

import pytest

from conftest import api_get, api_post, login, psql

ADMIN_EMAIL = "admin@leadradar.local"
SALES_EMAIL = "sales@leadradar.local"
ADMIN_DISPLAY_NAME = "admin"  # the local part of admin@leadradar.local (demo dataset)
APP_BASE_URL_DEFAULT = "http://localhost:8080"  # api.md#runtime default
PASSWORD_MIN_LENGTH = 12  # api.md#runtime default


@pytest.mark.ac("AC-78")
def test_admin_invites_a_sales_user_and_the_invite_is_accepted(invites_seeded_78):
    stack = invites_seeded_78
    base_url = stack["base_url"]
    env = stack["env"]

    _, admin = login(ADMIN_EMAIL, env["SEED_ADMIN_PASSWORD"], base_url=base_url)
    assert admin is not None

    invite_email = f"ac78-{uuid.uuid4().hex}@leadradar.local"
    created = api_post(
        "/invites", client=admin, base_url=base_url,
        json={"email": invite_email, "role": "SALES"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    invite, link = body["invite"], body["link"]

    # "a link under APP_BASE_URL carrying the token after #"
    assert link.startswith(f"{APP_BASE_URL_DEFAULT}/invite#"), link
    token = link.split("#", 1)[1]
    assert token

    assert invite["email"] == invite_email
    assert invite["role"] == "SALES"
    assert invite["invited_by"] == ADMIN_DISPLAY_NAME
    invite_id = invite["id"]

    # "the database holds only the token's hash"
    token_hash = psql(
        stack["project"], env, "leadradar", env["POSTGRES_PASSWORD"],
        f"SELECT token_hash FROM user_invite WHERE id = '{invite_id}';",
    ).stdout.strip()
    assert token_hash, "expected the invite row to exist"
    assert token_hash != token
    assert token not in token_hash

    # "an INVITE_CREATED row names the role"
    invite_created_audit = api_get(
        "/audit", client=admin, base_url=base_url,
        params={"kind": "USER", "action": "INVITE_CREATED", "entity_id": invite_id},
    )
    assert invite_created_audit.status_code == 200, invite_created_audit.text
    invite_created_items = invite_created_audit.json()["items"]
    assert len(invite_created_items) == 1, invite_created_items
    assert invite_created_items[0]["payload"]["role"] == "SALES", invite_created_items[0]

    # "with that token API-81 returns the email, role, inviter and expiry"
    preview = api_post("/auth/invite", base_url=base_url, json={"token": token})
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert preview_body["email"] == invite_email
    assert preview_body["role"] == "SALES"
    assert preview_body["invited_by"] == ADMIN_DISPLAY_NAME
    assert preview_body["expires_at"]
    assert preview_body["password_min_length"] == PASSWORD_MIN_LENGTH

    # "API-82 with a display name and a password of PASSWORD_MIN_LENGTH characters answers as
    # API-01 would, sets the session cookie, creates an active Sales user"
    password = "x" * PASSWORD_MIN_LENGTH
    accepted = api_post(
        "/auth/invite/accept", base_url=base_url,
        json={"token": token, "display_name": "AC-78 Invitee", "password": password},
    )
    assert accepted.status_code == 200, accepted.text
    assert "leadradar_session=" in accepted.headers.get("Set-Cookie", "")
    accepted_body = accepted.json()
    assert accepted_body["email"] == invite_email
    assert accepted_body["role"] == "SALES"
    new_user_id = accepted_body["id"]

    users = api_get("/users", client=admin, base_url=base_url)
    assert users.status_code == 200, users.text
    matching = [u for u in users.json() if u["id"] == new_user_id]
    assert len(matching) == 1, users.json()
    assert matching[0]["status"] == "ACTIVE"
    assert matching[0]["role"] == "SALES"

    # "writes USER_CREATED with the invite id and LOGIN_SUCCEEDED"
    user_created_audit = api_get(
        "/audit", client=admin, base_url=base_url,
        params={"kind": "USER", "action": "USER_CREATED", "entity_id": new_user_id},
    )
    assert user_created_audit.status_code == 200, user_created_audit.text
    user_created_items = user_created_audit.json()["items"]
    assert len(user_created_items) == 1, user_created_items
    assert user_created_items[0]["payload"]["invite_id"] == invite_id
    assert user_created_items[0]["payload"]["role"] == "SALES"

    login_succeeded_audit = api_get(
        "/audit", client=admin, base_url=base_url,
        params={"kind": "AUTH", "action": "LOGIN_SUCCEEDED", "entity_id": new_user_id},
    )
    assert login_succeeded_audit.status_code == 200, login_succeeded_audit.text
    assert len(login_succeeded_audit.json()["items"]) >= 1

    # "A Sales user calling API-79 is refused 403"
    _, sales = login(SALES_EMAIL, env["SEED_SALES_PASSWORD"], base_url=base_url)
    assert sales is not None
    refused = api_post(
        "/invites", client=sales, base_url=base_url,
        json={"email": f"ac78-blocked-{uuid.uuid4().hex}@leadradar.local", "role": "SALES"},
    )
    assert refused.status_code == 403, refused.text
