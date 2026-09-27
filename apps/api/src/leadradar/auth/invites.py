"""Invite links ([S-SEC-05](/requirements/system.md), `API-79` to `API-83`,
[ADR-21](/architecture/adrs/adr-21-invite-links-and-the-invite-scene.md)). Each function owns its
transaction; the token is never stored, only its hash."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from leadradar.audit.events import append_audit_event
from leadradar.auth.errors import (
    EmailTaken,
    InviteAlreadyPending,
    InviteNotFound,
    InviteNotPending,
)
from leadradar.auth.sessions import sign_in
from leadradar.auth.users import UserCreateData, add_user
from leadradar.core.enums import AppUserRole, AuditAction
from leadradar.core.invites import hash_invite_token, invite_expires_at, is_invite_pending
from leadradar.db.models.identity import AppUser, UserInvite


@dataclass(frozen=True)
class InviteView:
    """An invite with its inviter's display name ([`Invite`](/architecture/interfaces.md#invite),
    [`InvitePreview`](/architecture/interfaces.md#invitepreview))."""

    invite: UserInvite
    invited_by: str


def _pending(invite: UserInvite, now: datetime) -> bool:
    return is_invite_pending(
        accepted_at=invite.accepted_at,
        revoked_at=invite.revoked_at,
        expires_at=invite.expires_at,
        now=now,
    )


async def create_invite(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    email: str,
    role: AppUserRole,
    token: bytes,
    now: datetime,
    ttl_hours: int,
) -> InviteView:
    """`API-79`: refuses an email that belongs to a user or to a pending invite."""
    existing_user = (
        await db.execute(select(AppUser.id).where(AppUser.email == email))
    ).scalar_one_or_none()
    if existing_user is not None:
        raise EmailTaken(existing_user)
    for invite in (
        (await db.execute(select(UserInvite).where(UserInvite.email == email))).scalars().all()
    ):
        if _pending(invite, now):
            raise InviteAlreadyPending

    invite = UserInvite(
        email=email,
        role=role,
        token_hash=hash_invite_token(token),
        invited_by=actor_id,
        expires_at=invite_expires_at(now, ttl_hours),
        accepted_at=None,
        user_id=None,
        revoked_at=None,
    )
    db.add(invite)
    await db.flush()
    await append_audit_event(
        db,
        action=AuditAction.INVITE_CREATED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="user_invite",
        entity_id=invite.id,
        payload={"role": role.value},
    )
    inviter = (
        await db.execute(select(AppUser.display_name).where(AppUser.id == actor_id))
    ).scalar_one()
    await db.commit()
    await db.refresh(invite)
    return InviteView(invite=invite, invited_by=inviter)


async def list_pending_invites(db: AsyncSession, *, now: datetime) -> list[InviteView]:
    """`API-83`: the pending invites, newest first."""
    inviter = aliased(AppUser)
    rows: Sequence[tuple[UserInvite, str]] = (
        (
            await db.execute(
                select(UserInvite, inviter.display_name)
                .join(inviter, inviter.id == UserInvite.invited_by)
                .where(
                    UserInvite.accepted_at.is_(None),
                    UserInvite.revoked_at.is_(None),
                    UserInvite.expires_at > now,
                )
                .order_by(UserInvite.created_at.desc())
            )
        )
        .tuples()
        .all()
    )
    return [InviteView(invite=invite, invited_by=name) for invite, name in rows]


async def revoke_invite(
    db: AsyncSession, *, actor_id: uuid.UUID, invite_id: uuid.UUID, now: datetime
) -> None:
    """`API-80`."""
    invite = (
        await db.execute(select(UserInvite).where(UserInvite.id == invite_id).with_for_update())
    ).scalar_one_or_none()
    if invite is None:
        raise InviteNotFound
    if not _pending(invite, now):
        raise InviteNotPending
    invite.revoked_at = now
    await append_audit_event(
        db,
        action=AuditAction.INVITE_REVOKED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="user_invite",
        entity_id=invite.id,
        payload={},
    )
    await db.commit()


async def _pending_invite_by_token(
    db: AsyncSession, *, token: bytes, now: datetime, lock: bool
) -> InviteView:
    inviter = aliased(AppUser)
    query = (
        select(UserInvite, inviter.display_name)
        .join(inviter, inviter.id == UserInvite.invited_by)
        .where(UserInvite.token_hash == hash_invite_token(token))
    )
    if lock:
        query = query.with_for_update(of=UserInvite)
    row = (await db.execute(query)).tuples().first()
    if row is None or not _pending(row[0], now):
        raise InviteNotFound
    return InviteView(invite=row[0], invited_by=row[1])


async def preview_invite(db: AsyncSession, *, token: bytes, now: datetime) -> InviteView:
    """`API-81`."""
    return await _pending_invite_by_token(db, token=token, now=now, lock=False)


async def accept_invite(
    db: AsyncSession,
    *,
    token: bytes,
    display_name: str,
    password: str,
    now: datetime,
    session_token: bytes,
    password_min_length: int,
    max_failures: int,
    lock_minutes: int,
    session_ttl_hours: int,
) -> AppUser:
    """`API-82`: creates the active user of the invite's email and role, marks the invite
    accepted, then signs the user in exactly as `API-01` would."""
    view = await _pending_invite_by_token(db, token=token, now=now, lock=True)
    invite = view.invite
    # The Admin who invited stands behind the new account, so `USER_CREATED` names them.
    user = await add_user(
        db,
        actor_id=invite.invited_by,
        data=UserCreateData(
            email=invite.email, display_name=display_name, role=invite.role, password=password
        ),
        now=now,
        password_min_length=password_min_length,
        invite_id=invite.id,
    )
    invite.accepted_at = now
    invite.user_id = user.id
    await db.commit()
    return await sign_in(
        db,
        email=invite.email,
        password=password,
        now=now,
        token=session_token,
        max_failures=max_failures,
        lock_minutes=lock_minutes,
        session_ttl_hours=session_ttl_hours,
    )
