"""Session resolution over [`auth_session`](/architecture/sql-store.md#auth_session)
([Conventions](/architecture/interfaces.md#conventions) Authentication, G6 (a) of
`.work/lead-signal-feedback/task.md`): the smallest piece a route that needs to know who acted
requires. Plan task 2's `API-01` to `API-06` build sign-in, sign-out and session housekeeping on
top of this resolver; they must not write a second one."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AppUserRole, AppUserStatus
from leadradar.db.models.identity import AppUser, AuthSession


class Unauthenticated(Exception):
    """No session cookie, or no live session for its token: unknown, revoked, or expired at or
    before `now`."""


class Forbidden(Exception):
    """The session's user is `DISABLED`."""


@dataclass(frozen=True)
class Principal:
    """The signed-in user a live session resolves to."""

    user_id: uuid.UUID
    display_name: str
    role: AppUserRole


def hash_token(token: str) -> str:
    """The SHA-256 hex [`auth_session`](/architecture/sql-store.md#auth_session) `token_hash`
    stores; the plain token itself is never stored ([N-07](/requirements/system.md))."""
    return hashlib.sha256(token.encode()).hexdigest()


async def resolve_session(session: AsyncSession, token: str, now: datetime) -> Principal:
    """Looks up the live session for `token`'s hash and the user it belongs to. Raises
    `Unauthenticated` when no session matches, `Forbidden` when the user is `DISABLED`."""
    token_hash = hash_token(token)
    async with session.begin():
        row = (
            await session.execute(
                select(AppUser.id, AppUser.display_name, AppUser.role, AppUser.status)
                .join(AuthSession, AuthSession.user_id == AppUser.id)
                .where(
                    AuthSession.token_hash == token_hash,
                    AuthSession.revoked_at.is_(None),
                    AuthSession.expires_at > now,
                )
            )
        ).first()
    if row is None:
        raise Unauthenticated("No live session for this token.")
    user_id, display_name, role, status = row
    if status == AppUserStatus.DISABLED:
        raise Forbidden("This user is disabled.")
    return Principal(user_id=user_id, display_name=display_name, role=role)
