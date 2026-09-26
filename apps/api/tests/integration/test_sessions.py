"""Integration tests of [`auth/sessions.py`](/architecture/services/api.md#design) "Sessions and
passwords" (`S-SEC-01`, `API-01` to `API-03`)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.auth.errors import (
    AccountDisabled,
    AccountLocked,
    InvalidCredentials,
    Unauthenticated,
)
from leadradar.auth.passwords import hash_password
from leadradar.auth.sessions import authenticate, sign_in, sign_out
from leadradar.core.enums import AppUserRole, AppUserStatus, AuditAction
from leadradar.db.models.identity import AppUser, AuthSession
from leadradar.logs import request_id_var

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PASSWORD = "a-strong-enough-password"
MAX_FAILURES = 5
LOCK_MINUTES = 15
SESSION_TTL_HOURS = 12


async def _make_user(db: AsyncSession, **overrides: object) -> AppUser:
    values: dict[str, object] = {
        "email": f"user-{uuid.uuid4()}@example.com",
        "display_name": "Test User",
        "role": AppUserRole.SALES,
        "status": AppUserStatus.ACTIVE,
        "password_hash": hash_password(PASSWORD),
        "failed_logins": 0,
        "locked_until": None,
        "last_login_at": None,
    }
    values.update(overrides)
    user = AppUser(**values)
    db.add(user)
    await db.flush()
    return user


async def _sign_in(
    db: AsyncSession,
    email: str,
    password: str,
    *,
    now: datetime = NOW,
    token: bytes = b"\x01" * 32,
    max_failures: int = MAX_FAILURES,
    lock_minutes: int = LOCK_MINUTES,
    session_ttl_hours: int = SESSION_TTL_HOURS,
) -> AppUser:
    return await sign_in(
        db,
        email=email,
        password=password,
        now=now,
        token=token,
        max_failures=max_failures,
        lock_minutes=lock_minutes,
        session_ttl_hours=session_ttl_hours,
    )


async def test_sign_in_stores_only_the_token_hash_and_records_last_login_and_login_succeeded(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)

    await _sign_in(db_session, user.email, PASSWORD, token=b"\x02" * 32)

    session_row = (
        await db_session.execute(select(AuthSession).where(AuthSession.user_id == user.id))
    ).scalar_one()
    assert session_row.token_hash != (b"\x02" * 32).hex()
    assert len(session_row.token_hash) == 64

    refreshed = (
        await db_session.execute(select(AppUser).where(AppUser.id == user.id))
    ).scalar_one()
    assert refreshed.last_login_at == NOW

    audit_row = (
        (
            await db_session.execute(
                text("SELECT action, actor_id FROM audit_event WHERE entity_id = :id"),
                {"id": user.id},
            )
        )
        .mappings()
        .one()
    )
    assert audit_row["action"] == AuditAction.LOGIN_SUCCEEDED.value
    assert audit_row["actor_id"] == user.id


async def test_a_failed_sign_in_commits_its_count_and_login_failed_row_although_it_answers_an_error(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)

    with pytest.raises(InvalidCredentials):
        await _sign_in(db_session, user.email, "the-wrong-password")

    refreshed = (
        await db_session.execute(select(AppUser).where(AppUser.id == user.id))
    ).scalar_one()
    assert refreshed.failed_logins == 1

    count: int = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM audit_event WHERE entity_id = :id AND action = 'LOGIN_FAILED'"
            ),
            {"id": user.id},
        )
    ).scalar_one()
    assert count == 1


async def test_login_failed_has_a_null_actor_and_names_the_user_only_when_the_email_matches(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    unknown_email = f"unknown-{uuid.uuid4()}@example.com"

    with pytest.raises(InvalidCredentials):
        await _sign_in(db_session, user.email, "the-wrong-password")
    with pytest.raises(InvalidCredentials):
        await _sign_in(db_session, unknown_email, "whatever-password")

    # Filtered by this test's own user id, never by "every `LOGIN_FAILED` row": the shared
    # database also holds rows from every other test of the session (Risks, `design.md`).
    matched = (
        await db_session.execute(
            text(
                "SELECT actor_id FROM audit_event WHERE action = 'LOGIN_FAILED' AND entity_id = :id"
            ),
            {"id": user.id},
        )
    ).all()
    assert len(matched) == 1
    assert matched[0][0] is None

    unmatched_actor: uuid.UUID | None = (
        await db_session.execute(
            text(
                "SELECT actor_id FROM audit_event WHERE action = 'LOGIN_FAILED' "
                "AND entity_id IS NULL ORDER BY created_at DESC LIMIT 1"
            )
        )
    ).scalar_one()
    assert unmatched_actor is None


async def test_the_failure_reaching_the_maximum_locks_the_account(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, failed_logins=MAX_FAILURES - 1)

    with pytest.raises(AccountLocked) as excinfo:
        await _sign_in(db_session, user.email, "the-wrong-password")
    assert excinfo.value.retry_after_min == LOCK_MINUTES

    with pytest.raises(AccountLocked):
        await _sign_in(db_session, user.email, PASSWORD)


async def test_right_password_on_a_disabled_account_answers_account_disabled(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, status=AppUserStatus.DISABLED)

    with pytest.raises(AccountDisabled):
        await _sign_in(db_session, user.email, PASSWORD)


async def test_sign_out_revokes_the_session_and_appends_logout(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    token = b"\x03" * 32
    await _sign_in(db_session, user.email, PASSWORD, token=token)

    await sign_out(db_session, actor_id=user.id, token=token, now=NOW)

    session_row = (
        await db_session.execute(select(AuthSession).where(AuthSession.user_id == user.id))
    ).scalar_one()
    assert session_row.revoked_at == NOW

    logout_count: int = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM audit_event WHERE entity_id = :id AND action = 'LOGOUT' "
                "AND actor_id = :id"
            ),
            {"id": user.id},
        )
    ).scalar_one()
    assert logout_count == 1


async def test_authenticate_refuses_an_expired_or_revoked_session(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    token = b"\x04" * 32
    await _sign_in(db_session, user.email, PASSWORD, token=token, session_ttl_hours=1)

    authenticated = await authenticate(db_session, token=token, now=NOW)
    assert authenticated.id == user.id

    with pytest.raises(Unauthenticated):
        await authenticate(db_session, token=token, now=NOW + timedelta(hours=1))

    await sign_out(db_session, actor_id=user.id, token=token, now=NOW)
    with pytest.raises(Unauthenticated):
        await authenticate(db_session, token=token, now=NOW)


async def test_no_column_holds_a_plain_password_or_token_after_sign_in(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    token = b"\x05" * 32
    await _sign_in(db_session, user.email, PASSWORD, token=token)

    stored_hash = (
        await db_session.execute(select(AppUser.password_hash).where(AppUser.id == user.id))
    ).scalar_one()
    assert PASSWORD not in stored_hash

    stored_token_hash = (
        await db_session.execute(
            select(AuthSession.token_hash).where(AuthSession.user_id == user.id)
        )
    ).scalar_one()
    assert token.hex() not in stored_token_hash


async def test_audit_rows_carry_occurred_at_from_the_clock(db_session: AsyncSession) -> None:
    occurred_at = datetime(2026, 3, 1, tzinfo=UTC)
    await append_audit_event(
        db_session,
        action=AuditAction.LOGIN_SUCCEEDED,
        occurred_at=occurred_at,
        actor_id=None,
        entity_type=None,
        entity_id=None,
        payload={},
    )
    await db_session.commit()

    stored_occurred_at: datetime = (
        await db_session.execute(
            text("SELECT occurred_at FROM audit_event ORDER BY created_at DESC LIMIT 1")
        )
    ).scalar_one()
    assert stored_occurred_at == occurred_at


async def test_audit_rows_carry_the_request_id_bound_for_the_request(
    db_session: AsyncSession,
) -> None:
    token = request_id_var.set("a-request-id")
    try:
        await append_audit_event(
            db_session,
            action=AuditAction.LOGIN_SUCCEEDED,
            occurred_at=NOW,
            actor_id=None,
            entity_type=None,
            entity_id=None,
            payload={},
        )
        await db_session.commit()
    finally:
        request_id_var.reset(token)

    stored_request_id: str = (
        await db_session.execute(
            text("SELECT request_id FROM audit_event ORDER BY created_at DESC LIMIT 1")
        )
    ).scalar_one()
    assert stored_request_id == "a-request-id"


async def test_concurrent_wrong_passwords_lock_the_account_exactly_at_the_maximum(
    async_engine: AsyncEngine,
) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    setup_session = AsyncSession(async_engine, expire_on_commit=False)
    try:
        user = await _make_user(setup_session, email=email, failed_logins=MAX_FAILURES - 2)
        await setup_session.commit()
        user_id = user.id

        async def _attempt() -> None:
            session = AsyncSession(async_engine, expire_on_commit=False)
            try:
                with pytest.raises((InvalidCredentials, AccountLocked)):
                    await _sign_in(session, email, "the-wrong-password")
            finally:
                await session.close()

        await asyncio.gather(_attempt(), _attempt())

        check_session = AsyncSession(async_engine, expire_on_commit=False)
        try:
            refreshed = (
                await check_session.execute(select(AppUser).where(AppUser.id == user_id))
            ).scalar_one()
            assert refreshed.locked_until is not None
            assert refreshed.failed_logins == 0
        finally:
            await check_session.close()
    finally:
        # `audit_event` is append-only for the application role (G1): its stray `LOGIN_FAILED`
        # rows are left in place, harmless since `entity_id` carries no foreign key.
        await setup_session.execute(
            text("DELETE FROM auth_session WHERE user_id = :id"), {"id": user.id}
        )
        await setup_session.execute(text("DELETE FROM app_user WHERE id = :id"), {"id": user.id})
        await setup_session.commit()
        await setup_session.close()
