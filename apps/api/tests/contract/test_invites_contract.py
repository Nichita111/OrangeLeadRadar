"""Contract tests of `API-79` to `API-83` ([Authentication and users](
/architecture/interfaces.md#authentication-and-users), `S-SEC-05`, `AC-78`, `AC-79`)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.identity import AppUser, UserInvite
from leadradar.settings import ApiSettings
from tests.contract.conftest import PASSWORD, _http_client

pytestmark = pytest.mark.contract

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def _email() -> str:
    return f"invitee-{uuid.uuid4()}@example.com"


async def _invite(admin_client: httpx.AsyncClient, email: str, role: str = "SALES") -> dict:
    response = await admin_client.post("/api/v1/invites", json={"email": email, "role": role})
    assert response.status_code == 200, response.text
    return response.json()


def _token(created: dict) -> str:
    return created["link"].split("#", 1)[1]


async def _audit(app: FastAPI, entity_id: str, action: str) -> list[AuditEvent]:
    async with AsyncSession(app.state.engine) as db:
        return list(
            (
                await db.execute(
                    select(AuditEvent).where(
                        AuditEvent.entity_id == uuid.UUID(entity_id), AuditEvent.action == action
                    )
                )
            )
            .scalars()
            .all()
        )


async def test_invite_returns_a_fragment_link_once_and_stores_only_the_hash(
    running_app: FastAPI, admin_client: httpx.AsyncClient, api_settings: ApiSettings
) -> None:
    email = _email()
    created = await _invite(admin_client, email)

    assert set(created) == {"invite", "link"}
    assert set(created["invite"]) == {
        "id",
        "email",
        "role",
        "invited_by",
        "created_at",
        "expires_at",
    }
    assert created["invite"]["email"] == email
    assert created["invite"]["role"] == "SALES"
    assert created["link"].startswith(f"{api_settings.app_base_url.rstrip('/')}/invite#")
    token = _token(created)
    async with AsyncSession(running_app.state.engine) as db:
        row = (await db.execute(select(UserInvite).where(UserInvite.email == email))).scalar_one()
    assert row.token_hash == hashlib.sha256(bytes.fromhex(token)).hexdigest()
    assert token not in row.token_hash
    events = await _audit(running_app, created["invite"]["id"], "INVITE_CREATED")
    assert [event.payload for event in events] == [{"role": "SALES"}]

    listed = await admin_client.get("/api/v1/invites")
    assert listed.status_code == 200
    ids = [invite["id"] for invite in listed.json()]
    assert created["invite"]["id"] in ids
    assert all("link" not in invite for invite in listed.json())


async def test_invites_are_admin_only(sales_client: httpx.AsyncClient) -> None:
    assert (
        await sales_client.post("/api/v1/invites", json={"email": _email(), "role": "SALES"})
    ).status_code == 403
    assert (await sales_client.get("/api/v1/invites")).status_code == 403


async def test_preview_then_accept_creates_and_signs_in_the_invited_user(
    running_app: FastAPI, admin_client: httpx.AsyncClient, api_settings: ApiSettings
) -> None:
    email = _email()
    created = await _invite(admin_client, email, role="SALES")
    token = _token(created)

    async with _http_client(running_app, headers=HEADERS) as anonymous:
        preview = await anonymous.post("/api/v1/auth/invite", json={"token": token})
        assert preview.status_code == 200
        body = preview.json()
        assert body["email"] == email
        assert body["role"] == "SALES"
        assert body["invited_by"] == created["invite"]["invited_by"]
        assert body["password_min_length"] == api_settings.password_min_length

        accepted = await anonymous.post(
            "/api/v1/auth/invite/accept",
            json={"token": token, "display_name": "New Seller", "password": PASSWORD},
        )
        assert accepted.status_code == 200, accepted.text
        user = accepted.json()
        assert set(user) == {"id", "email", "display_name", "role"}
        assert user["email"] == email
        assert user["display_name"] == "New Seller"
        assert user["role"] == "SALES"
        cookie = accepted.cookies["leadradar_session"]
        me = await anonymous.get(
            "/api/v1/auth/me", headers={"Cookie": f"leadradar_session={cookie}"}
        )
        assert me.status_code == 200
        assert me.json()["id"] == user["id"]

    created_rows = await _audit(running_app, user["id"], "USER_CREATED")
    assert [event.payload for event in created_rows] == [
        {"role": "SALES", "invite_id": created["invite"]["id"]}
    ]
    assert len(await _audit(running_app, user["id"], "LOGIN_SUCCEEDED")) == 1
    async with AsyncSession(running_app.state.engine) as db:
        assert (
            await db.execute(select(AppUser.status).where(AppUser.email == email))
        ).scalar_one() == "ACTIVE"


async def test_a_used_link_no_longer_works(
    running_app: FastAPI, admin_client: httpx.AsyncClient
) -> None:
    token = _token(await _invite(admin_client, _email()))
    async with _http_client(running_app, headers=HEADERS) as anonymous:
        first = await anonymous.post(
            "/api/v1/auth/invite/accept",
            json={"token": token, "display_name": "Once", "password": PASSWORD},
        )
        assert first.status_code == 200
        again = await anonymous.post(
            "/api/v1/auth/invite/accept",
            json={"token": token, "display_name": "Twice", "password": PASSWORD},
        )
        assert again.status_code == 404
        assert again.json()["error"]["code"] == "NOT_FOUND"
        assert (
            await anonymous.post("/api/v1/auth/invite", json={"token": token})
        ).status_code == 404


async def test_a_revoked_link_no_longer_works_and_revoking_twice_conflicts(
    running_app: FastAPI, admin_client: httpx.AsyncClient
) -> None:
    created = await _invite(admin_client, _email())
    invite_id = created["invite"]["id"]

    revoked = await admin_client.post(f"/api/v1/invites/{invite_id}/revoke")
    assert revoked.status_code == 204
    assert len(await _audit(running_app, invite_id, "INVITE_REVOKED")) == 1
    assert (await admin_client.post(f"/api/v1/invites/{invite_id}/revoke")).status_code == 409
    listed = await admin_client.get("/api/v1/invites")
    assert invite_id not in [invite["id"] for invite in listed.json()]

    async with _http_client(running_app, headers=HEADERS) as anonymous:
        preview = await anonymous.post("/api/v1/auth/invite", json={"token": _token(created)})
        assert preview.status_code == 404


async def test_an_expired_link_no_longer_works(
    running_app: FastAPI, admin_client: httpx.AsyncClient, api_settings: ApiSettings
) -> None:
    created = await _invite(admin_client, _email())
    later = datetime.now(tz=UTC) + timedelta(hours=api_settings.invite_ttl_hours, minutes=1)
    running_app.state.clock = lambda: later

    async with _http_client(running_app, headers=HEADERS) as anonymous:
        accepted = await anonymous.post(
            "/api/v1/auth/invite/accept",
            json={"token": _token(created), "display_name": "Late", "password": PASSWORD},
        )
    assert accepted.status_code == 404


async def test_an_unknown_or_malformed_token_is_not_found(running_app: FastAPI) -> None:
    async with _http_client(running_app, headers=HEADERS) as anonymous:
        for token in ("00" * 32, "not-hex"):
            response = await anonymous.post("/api/v1/auth/invite", json={"token": token})
            assert response.status_code == 404


async def test_inviting_a_user_or_a_pending_email_conflicts(
    admin_client: httpx.AsyncClient, sales_user: tuple[uuid.UUID, str, str]
) -> None:
    _, existing_email, _ = sales_user
    taken = await admin_client.post(
        "/api/v1/invites", json={"email": existing_email, "role": "SALES"}
    )
    assert taken.status_code == 409

    email = _email()
    await _invite(admin_client, email)
    pending = await admin_client.post("/api/v1/invites", json={"email": email, "role": "ADMIN"})
    assert pending.status_code == 409
    assert pending.json()["error"]["code"] == "CONFLICT"


async def test_a_short_password_is_a_field_error_and_leaves_the_invite_pending(
    running_app: FastAPI, admin_client: httpx.AsyncClient
) -> None:
    created = await _invite(admin_client, _email())
    token = _token(created)
    async with _http_client(running_app, headers=HEADERS) as anonymous:
        short = await anonymous.post(
            "/api/v1/auth/invite/accept",
            json={"token": token, "display_name": "Short", "password": "eleven-chr"},
        )
        assert short.status_code == 422
        assert short.json()["error"]["details"]["fields"][0]["field"] == "password"
        assert (
            await anonymous.post("/api/v1/auth/invite", json={"token": token})
        ).status_code == 200
