"""AC-79 (docs/requirements/acceptance.md):
"Given an invite, when it has been accepted, revoked with `API-80` or is past
`INVITE_TTL_HOURS`, then `API-81` and `API-82` with its token answer `404 NOT_FOUND` and create
no user; inviting an email that already has a user or a pending invite answers `409 CONFLICT`; a
password shorter than `PASSWORD_MIN_LENGTH` answers `422 VALIDATION` on `password` and leaves the
invite pending; no log line or audit payload contains a token."

Driven through `API-79`/`API-80`/`API-81`/`API-82`/`API-83`/`API-04`/`API-60`
(docs/architecture/interfaces.md#authentication-and-users-contracts,
docs/architecture/interfaces.md#audit-and-health-contracts) of a fresh module stack
(tests/acceptance/docker/compose.override.invites.yml), whose clock this test advances past
`INVITE_TTL_HOURS` (`72`, docs/architecture/services/api.md#runtime default) for the expiry case
(docs/architecture/services/worker.md#runtime: `CLOCK_FILE` is "read on every use of the
clock").  Container logs are read with `docker compose logs` for the "no log line ... contains a
token" half.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from conftest import (
    INVITES_CLOCK_START,
    INVITES_OVERRIDE_COMPOSE,
    api_get,
    api_post,
    compose,
    login,
    set_clock,
)

ADMIN_EMAIL = "admin@leadradar.local"
PASSWORD_MIN_LENGTH = 12  # api.md#runtime default
INVITE_TTL_HOURS = 72  # api.md#runtime default


def _create_invite(admin, base_url: str, email: str) -> tuple[str, str, str]:
    """Returns (invite_id, token, link)."""
    created = api_post(
        "/invites", client=admin, base_url=base_url, json={"email": email, "role": "SALES"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    token = body["link"].split("#", 1)[1]
    return body["invite"]["id"], token, body["link"]


@pytest.mark.ac("AC-79")
def test_an_accepted_revoked_expired_conflicting_or_weak_invite_is_refused_and_leaks_no_token(
    invites_seeded_79,
):
    stack = invites_seeded_79
    base_url = stack["base_url"]
    env = stack["env"]
    project = stack["project"]
    tokens_seen: list[str] = []

    _, admin = login(ADMIN_EMAIL, env["SEED_ADMIN_PASSWORD"], base_url=base_url)
    assert admin is not None

    # --- "it has been accepted" -> API-81 and API-82 with its token answer 404, no user is
    # created a second time.
    accepted_email = f"ac79-accepted-{uuid.uuid4().hex}@leadradar.local"
    accepted_invite_id, accepted_token, _ = _create_invite(admin, base_url, accepted_email)
    tokens_seen.append(accepted_token)

    first_accept = api_post(
        "/auth/invite/accept", base_url=base_url,
        json={"token": accepted_token, "display_name": "AC-79 Accepted", "password": "x" * PASSWORD_MIN_LENGTH},
    )
    assert first_accept.status_code == 200, first_accept.text

    reused_preview = api_post("/auth/invite", base_url=base_url, json={"token": accepted_token})
    assert reused_preview.status_code == 404, reused_preview.text

    reused_accept = api_post(
        "/auth/invite/accept", base_url=base_url,
        json={"token": accepted_token, "display_name": "AC-79 Reused", "password": "y" * PASSWORD_MIN_LENGTH},
    )
    assert reused_accept.status_code == 404, reused_accept.text

    users_after_reuse = api_get("/users", client=admin, base_url=base_url)
    assert users_after_reuse.status_code == 200
    matching_accepted = [u for u in users_after_reuse.json() if u["email"] == accepted_email]
    assert len(matching_accepted) == 1, "the reused token must create no second user"

    # --- "revoked with API-80" -> API-81 and API-82 with its token answer 404, no user created.
    revoked_email = f"ac79-revoked-{uuid.uuid4().hex}@leadradar.local"
    revoked_invite_id, revoked_token, _ = _create_invite(admin, base_url, revoked_email)
    tokens_seen.append(revoked_token)

    revoke = api_post(f"/invites/{revoked_invite_id}/revoke", client=admin, base_url=base_url)
    assert revoke.status_code == 204, revoke.text

    revoked_preview = api_post("/auth/invite", base_url=base_url, json={"token": revoked_token})
    assert revoked_preview.status_code == 404, revoked_preview.text

    revoked_accept = api_post(
        "/auth/invite/accept", base_url=base_url,
        json={"token": revoked_token, "display_name": "AC-79 Revoked", "password": "z" * PASSWORD_MIN_LENGTH},
    )
    assert revoked_accept.status_code == 404, revoked_accept.text

    users_after_revoked = api_get("/users", client=admin, base_url=base_url)
    assert users_after_revoked.status_code == 200
    assert not any(u["email"] == revoked_email for u in users_after_revoked.json())

    # --- "inviting an email that already has a user ... answers 409 CONFLICT" (accepted_email
    # now belongs to an active user).
    conflict_user = api_post(
        "/invites", client=admin, base_url=base_url,
        json={"email": accepted_email, "role": "SALES"},
    )
    assert conflict_user.status_code == 409, conflict_user.text

    # --- "... or a pending invite answers 409 CONFLICT".
    pending_email = f"ac79-pending-{uuid.uuid4().hex}@leadradar.local"
    _pending_invite_id, pending_token, _ = _create_invite(admin, base_url, pending_email)
    tokens_seen.append(pending_token)

    conflict_pending = api_post(
        "/invites", client=admin, base_url=base_url,
        json={"email": pending_email, "role": "SALES"},
    )
    assert conflict_pending.status_code == 409, conflict_pending.text

    # --- "a password shorter than PASSWORD_MIN_LENGTH answers 422 VALIDATION on password and
    # leaves the invite pending".
    weak_email = f"ac79-weak-{uuid.uuid4().hex}@leadradar.local"
    weak_invite_id, weak_token, _ = _create_invite(admin, base_url, weak_email)
    tokens_seen.append(weak_token)

    weak_accept = api_post(
        "/auth/invite/accept", base_url=base_url,
        json={
            "token": weak_token, "display_name": "AC-79 Weak",
            "password": "x" * (PASSWORD_MIN_LENGTH - 1),
        },
    )
    assert weak_accept.status_code == 422, weak_accept.text
    weak_error = weak_accept.json()["error"]
    assert weak_error["code"] == "VALIDATION", weak_error
    field_names = {f["field"] for f in weak_error["details"]["fields"]}
    assert "password" in field_names, weak_error

    # "leaves the invite pending" - still previewable, and no user was created for it.
    still_pending_preview = api_post("/auth/invite", base_url=base_url, json={"token": weak_token})
    assert still_pending_preview.status_code == 200, still_pending_preview.text
    pending_invites = api_get("/invites", client=admin, base_url=base_url)
    assert pending_invites.status_code == 200
    assert any(i["id"] == weak_invite_id for i in pending_invites.json())
    users_after_weak = api_get("/users", client=admin, base_url=base_url)
    assert not any(u["email"] == weak_email for u in users_after_weak.json())

    # --- "is past INVITE_TTL_HOURS" -> API-81 and API-82 with its token answer 404, no user
    # created. Done last: advancing the clock expires every session issued before it, including
    # the admin's above.
    expired_email = f"ac79-expired-{uuid.uuid4().hex}@leadradar.local"
    expired_invite_id, expired_token, _ = _create_invite(admin, base_url, expired_email)
    tokens_seen.append(expired_token)

    start = datetime.strptime(INVITES_CLOCK_START, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    past_ttl = start + timedelta(hours=INVITE_TTL_HOURS + 1)
    set_clock(stack["clock_dir"], past_ttl.strftime("%Y-%m-%dT%H:%M:%SZ"))

    expired_preview = api_post("/auth/invite", base_url=base_url, json={"token": expired_token})
    assert expired_preview.status_code == 404, expired_preview.text

    expired_accept = api_post(
        "/auth/invite/accept", base_url=base_url,
        json={"token": expired_token, "display_name": "AC-79 Expired", "password": "w" * PASSWORD_MIN_LENGTH},
    )
    assert expired_accept.status_code == 404, expired_accept.text

    # A fresh sign-in: the pre-expiry admin session above no longer authenticates once the clock
    # has moved past its SESSION_TTL_HOURS.
    _, admin_after = login(ADMIN_EMAIL, env["SEED_ADMIN_PASSWORD"], base_url=base_url)
    assert admin_after is not None
    users_after_expired = api_get("/users", client=admin_after, base_url=base_url)
    assert users_after_expired.status_code == 200
    assert not any(u["email"] == expired_email for u in users_after_expired.json())

    # --- "no log line or audit payload contains a token".
    all_audit = api_get("/audit", client=admin_after, base_url=base_url, params={"page_size": 200})
    assert all_audit.status_code == 200, all_audit.text
    audit_dump = json.dumps(all_audit.json())
    for token in tokens_seen:
        assert token not in audit_dump, f"audit payload leaks an invite token: {token!r}"

    logs = compose(
        project, "logs", "--no-color", "--no-log-prefix", "api", "worker",
        env=env, capture=True, check=False, overlay=INVITES_OVERRIDE_COMPOSE,
    ).stdout
    for token in tokens_seen:
        assert token not in logs, f"a log line leaks an invite token: {token!r}"
