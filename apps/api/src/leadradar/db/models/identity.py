"""[Identity](/architecture/sql-store.md#identity): `app_user`, `auth_session`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from leadradar.core.enums import AppUserRole, AppUserStatus
from leadradar.db.base import TimestampedBase
from leadradar.db.types import fk_uuid, pg_enum


class AppUser(TimestampedBase):
    """[`app_user`](/architecture/sql-store.md#app_user)."""

    __tablename__ = "app_user"

    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    display_name: Mapped[str]
    role: Mapped[AppUserRole] = mapped_column(pg_enum(AppUserRole, "app_user_role"))
    status: Mapped[AppUserStatus] = mapped_column(pg_enum(AppUserStatus, "app_user_status"))
    password_hash: Mapped[str]
    failed_logins: Mapped[int]
    locked_until: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]


class AuthSession(TimestampedBase):
    """[`auth_session`](/architecture/sql-store.md#auth_session)."""

    __tablename__ = "auth_session"

    user_id: Mapped[uuid.UUID] = fk_uuid("app_user.id")
    token_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
