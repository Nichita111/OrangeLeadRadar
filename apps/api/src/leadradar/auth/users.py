"""User management ([S-SEC-03](/requirements/system.md), `API-04` to `API-06`)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.auth.errors import EmailTaken, PasswordTooShort, SelfChangeRefused, UserNotFound
from leadradar.auth.passwords import hash_password
from leadradar.core.enums import AppUserRole, AppUserStatus, AuditAction
from leadradar.core.sign_in import changed_fields, refuse_self_change
from leadradar.db.models.identity import AppUser, AuthSession


@dataclass(frozen=True)
class UserCreateData:
    """[`UserCreate`](/architecture/interfaces.md#usercreate)."""

    email: str
    display_name: str
    role: AppUserRole
    password: str


@dataclass(frozen=True)
class UserUpdateData:
    """[`UserUpdate`](/architecture/interfaces.md#userupdate); a field left `None` was not sent
    (no field of the shape accepts an explicit null)."""

    display_name: str | None = None
    role: AppUserRole | None = None
    status: AppUserStatus | None = None
    password: str | None = None

    def sent_fields(self) -> dict[str, object]:
        values: dict[str, object] = {
            "display_name": self.display_name,
            "role": self.role,
            "status": self.status,
            "password": self.password,
        }
        return {field: value for field, value in values.items() if value is not None}


def _require_password_min_length(password: str, minimum: int) -> None:
    """The one place [`UserCreate`](/architecture/interfaces.md#usercreate) and
    [`UserUpdate`](/architecture/interfaces.md#userupdate) `password`'s `PASSWORD_MIN_LENGTH`
    minimum is enforced; every caller (`API-05`, `API-06`, the seed) shares it."""
    if len(password) < minimum:
        raise PasswordTooShort(minimum)


async def list_users(db: AsyncSession) -> Sequence[AppUser]:
    """`API-04`, ordered by `display_name` (G8)."""
    return (await db.execute(select(AppUser).order_by(AppUser.display_name))).scalars().all()


async def create_user(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    data: UserCreateData,
    now: datetime,
    password_min_length: int,
) -> AppUser:
    """`API-05`. `actor_id` is null when seeding ([Demo dataset](
    /architecture/overview.md#demo-dataset), G4)."""
    _require_password_min_length(data.password, password_min_length)
    user = AppUser(
        email=data.email,
        display_name=data.display_name,
        role=data.role,
        status=AppUserStatus.ACTIVE,
        password_hash=hash_password(data.password),
        failed_logins=0,
        locked_until=None,
        last_login_at=None,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing_id = (
            await db.execute(select(AppUser.id).where(AppUser.email == data.email))
        ).scalar_one()
        raise EmailTaken(existing_id) from None

    await append_audit_event(
        db,
        action=AuditAction.USER_CREATED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="app_user",
        entity_id=user.id,
        payload={"role": data.role.value},
    )
    await db.commit()
    return user


async def update_user(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    data: UserUpdateData,
    now: datetime,
    password_min_length: int,
) -> AppUser:
    """`API-06`: refuses an Admin's own role or status change (`S-SEC-03`), revokes every open
    session on disabling, and writes no audit row when nothing changed (G8)."""
    if data.password is not None:
        _require_password_min_length(data.password, password_min_length)
    user = (
        await db.execute(select(AppUser).where(AppUser.id == user_id).with_for_update())
    ).scalar_one_or_none()
    if user is None:
        raise UserNotFound

    update = data.sent_fields()
    if refuse_self_change(actor_id, user_id, update, current_role=user.role):
        raise SelfChangeRefused

    current = {
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
    }
    changes = changed_fields(current, update)

    if "display_name" in changes:
        assert data.display_name is not None
        user.display_name = data.display_name
    if "role" in changes:
        assert data.role is not None
        user.role = data.role
    disables_sessions = False
    if "status" in changes:
        assert data.status is not None
        user.status = data.status
        disables_sessions = data.status is AppUserStatus.DISABLED
    if data.password is not None:
        user.password_hash = hash_password(data.password)

    if disables_sessions:
        open_sessions = (
            (
                await db.execute(
                    select(AuthSession).where(
                        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
                    )
                )
            )
            .scalars()
            .all()
        )
        for session_row in open_sessions:
            session_row.revoked_at = now

    if changes:
        await append_audit_event(
            db,
            action=AuditAction.USER_UPDATED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type="app_user",
            entity_id=user.id,
            payload=changes,
        )

    await db.commit()
    return user
