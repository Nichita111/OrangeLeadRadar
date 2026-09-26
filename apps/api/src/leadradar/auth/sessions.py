"""Sign-in, sign-out and session authentication ([S-SEC-01](/requirements/system.md), `API-01`
to `API-03`). Each function owns its transaction (api Design "Transactions"): the failed
sign-in's counters, lock and `LOGIN_FAILED` row are committed before the typed error is raised,
so they survive the `401` or `423` ([api Design](/architecture/services/api.md#design) "Sessions
and passwords")."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.auth.errors import (
    AccountDisabled,
    AccountLocked,
    Forbidden,
    InvalidCredentials,
    Unauthenticated,
)
from leadradar.auth.passwords import verify_password
from leadradar.core.enums import AppUserStatus, AuditAction
from leadradar.core.sign_in import (
    LoginFailedReason,
    SignInOutcome,
    UserAuthState,
    decide_sign_in,
    hash_session_token,
    is_session_valid,
    session_expires_at,
)
from leadradar.db.models.identity import AppUser, AuthSession


async def sign_in(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    now: datetime,
    token: bytes,
    max_failures: int,
    lock_minutes: int,
    session_ttl_hours: int,
) -> AppUser:
    """`API-01`. Raises `InvalidCredentials`, `AccountLocked` or `AccountDisabled` after
    committing the write its outcome makes."""
    user = (
        await db.execute(select(AppUser).where(AppUser.email == email).with_for_update())
    ).scalar_one_or_none()

    if user is None:
        await append_audit_event(
            db,
            action=AuditAction.LOGIN_FAILED,
            occurred_at=now,
            actor_id=None,
            entity_type=None,
            entity_id=None,
            payload={"reason": LoginFailedReason.BAD_CREDENTIALS.value},
        )
        await db.commit()
        raise InvalidCredentials

    password_matches = verify_password(password, user.password_hash)
    state = UserAuthState(
        status=user.status, failed_logins=user.failed_logins, locked_until=user.locked_until
    )
    decision = decide_sign_in(state, password_matches, now, max_failures, lock_minutes)

    user.failed_logins = decision.failed_logins
    user.locked_until = decision.locked_until

    if decision.outcome is SignInOutcome.SUCCEEDED:
        user.last_login_at = now
        db.add(
            AuthSession(
                user_id=user.id,
                token_hash=hash_session_token(token),
                expires_at=session_expires_at(now, session_ttl_hours),
                revoked_at=None,
            )
        )
        await append_audit_event(
            db,
            action=AuditAction.LOGIN_SUCCEEDED,
            occurred_at=now,
            actor_id=user.id,
            entity_type="app_user",
            entity_id=user.id,
            payload={},
        )
        await db.commit()
        return user

    assert decision.reason is not None
    await append_audit_event(
        db,
        action=AuditAction.LOGIN_FAILED,
        occurred_at=now,
        actor_id=None,
        entity_type="app_user",
        entity_id=user.id,
        payload={"reason": decision.reason.value},
    )
    await db.commit()

    if decision.outcome is SignInOutcome.LOCKED:
        assert decision.retry_after_min is not None
        raise AccountLocked(decision.retry_after_min)
    if decision.outcome is SignInOutcome.DISABLED:
        raise AccountDisabled
    raise InvalidCredentials


async def sign_out(db: AsyncSession, *, actor_id: uuid.UUID, token: bytes, now: datetime) -> None:
    """`API-02`: revokes the session the cookie names and appends `LOGOUT`."""
    token_hash = hash_session_token(token)
    session_row = (
        await db.execute(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash, AuthSession.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if session_row is not None:
        session_row.revoked_at = now

    await append_audit_event(
        db,
        action=AuditAction.LOGOUT,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="app_user",
        entity_id=actor_id,
        payload={},
    )
    await db.commit()


async def authenticate(db: AsyncSession, *, token: bytes, now: datetime) -> AppUser:
    """Backs `current_user`: loads the session the cookie names, valid and not revoked; a
    `DISABLED` user's session raises `Forbidden`."""
    row = (
        await db.execute(
            select(AuthSession, AppUser)
            .join(AppUser, AppUser.id == AuthSession.user_id)
            .where(AuthSession.token_hash == hash_session_token(token))
        )
    ).first()
    if row is None:
        raise Unauthenticated
    session_row, user = row
    if not is_session_valid(session_row.expires_at, session_row.revoked_at, now):
        raise Unauthenticated
    if user.status is AppUserStatus.DISABLED:
        raise Forbidden
    return user
