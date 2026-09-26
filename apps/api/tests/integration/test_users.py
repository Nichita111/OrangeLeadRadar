"""Integration tests of [`auth/users.py`](/architecture/services/api.md#design) (`S-SEC-03`,
`API-04` to `API-06`)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.auth.errors import EmailTaken, SelfChangeRefused, UserNotFound
from leadradar.auth.passwords import verify_password
from leadradar.auth.sessions import sign_in
from leadradar.auth.users import (
    UserCreateData,
    UserUpdateData,
    create_user,
    list_users,
    update_user,
)
from leadradar.core.enums import AppUserRole, AppUserStatus
from leadradar.db.models.identity import AppUser, AuthSession
from leadradar.settings import ApiSettings

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PASSWORD = "a-strong-enough-password"


@pytest.fixture
def password_min_length(api_settings: ApiSettings) -> int:
    """`PASSWORD_MIN_LENGTH` ([api Runtime](/architecture/services/api.md#runtime)), the one
    value `create_user`/`update_user` enforce their password rule from."""
    return api_settings.password_min_length


async def _create(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
    password_min_length: int,
    **overrides: Any,
) -> AppUser:
    defaults: dict[str, Any] = {
        "email": f"user-{uuid.uuid4()}@example.com",
        "display_name": "A User",
        "role": AppUserRole.SALES,
        "password": PASSWORD,
    }
    defaults.update(overrides)
    return await create_user(
        db,
        actor_id=actor_id,
        data=UserCreateData(**defaults),
        now=NOW,
        password_min_length=password_min_length,
    )


async def test_create_user_hashes_the_password_and_records_user_created(
    db_session: AsyncSession, password_min_length: int
) -> None:
    actor = await _create(
        db_session, role=AppUserRole.ADMIN, password_min_length=password_min_length
    )
    actor_id = actor.id
    user = await _create(
        db_session,
        actor_id=actor_id,
        role=AppUserRole.ADMIN,
        password_min_length=password_min_length,
    )

    assert verify_password(PASSWORD, user.password_hash)
    assert user.status == AppUserStatus.ACTIVE
    assert user.failed_logins == 0

    row = (
        (
            await db_session.execute(
                text("SELECT action, actor_id, payload FROM audit_event WHERE entity_id = :id"),
                {"id": user.id},
            )
        )
        .mappings()
        .one()
    )
    assert row["action"] == "USER_CREATED"
    assert row["actor_id"] == actor_id
    assert row["payload"] == {"role": "ADMIN"}


async def test_seeding_creates_a_user_created_row_with_a_null_actor(
    db_session: AsyncSession, password_min_length: int
) -> None:
    user = await _create(db_session, actor_id=None, password_min_length=password_min_length)

    actor_id: uuid.UUID | None = (
        await db_session.execute(
            text("SELECT actor_id FROM audit_event WHERE entity_id = :id"), {"id": user.id}
        )
    ).scalar_one()
    assert actor_id is None


async def test_creating_a_user_with_an_email_differing_only_in_case_conflicts_by_id(
    db_session: AsyncSession, password_min_length: int
) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    existing = await _create(db_session, email=email, password_min_length=password_min_length)
    existing_id = existing.id  # captured before the conflict's own rollback expires it

    with pytest.raises(EmailTaken) as excinfo:
        await _create(db_session, email=email.upper(), password_min_length=password_min_length)
    assert excinfo.value.entity_id == existing_id


async def test_users_are_listed_by_display_name(
    db_session: AsyncSession, password_min_length: int
) -> None:
    unique = uuid.uuid4().hex[:8]
    await _create(
        db_session, display_name=f"{unique}-Zebra", password_min_length=password_min_length
    )
    await _create(
        db_session, display_name=f"{unique}-Apple", password_min_length=password_min_length
    )

    users = await list_users(db_session)
    names = [user.display_name for user in users if user.display_name.startswith(unique)]
    assert names == sorted(names)


async def test_admin_demoting_or_disabling_themselves_is_refused(
    db_session: AsyncSession, password_min_length: int
) -> None:
    admin = await _create(
        db_session, role=AppUserRole.ADMIN, password_min_length=password_min_length
    )

    with pytest.raises(SelfChangeRefused):
        await update_user(
            db_session,
            actor_id=admin.id,
            user_id=admin.id,
            data=UserUpdateData(role=AppUserRole.SALES),
            now=NOW,
            password_min_length=password_min_length,
        )
    with pytest.raises(SelfChangeRefused):
        await update_user(
            db_session,
            actor_id=admin.id,
            user_id=admin.id,
            data=UserUpdateData(status=AppUserStatus.DISABLED),
            now=NOW,
            password_min_length=password_min_length,
        )


async def test_admin_may_change_their_own_name_and_password(
    db_session: AsyncSession, password_min_length: int
) -> None:
    admin = await _create(
        db_session, role=AppUserRole.ADMIN, password_min_length=password_min_length
    )

    updated = await update_user(
        db_session,
        actor_id=admin.id,
        user_id=admin.id,
        data=UserUpdateData(display_name="New Name", role=AppUserRole.ADMIN),
        now=NOW,
        password_min_length=password_min_length,
    )
    assert updated.display_name == "New Name"


async def test_an_unknown_user_id_answers_user_not_found(
    db_session: AsyncSession, password_min_length: int
) -> None:
    actor = await _create(
        db_session, role=AppUserRole.ADMIN, password_min_length=password_min_length
    )
    with pytest.raises(UserNotFound):
        await update_user(
            db_session,
            actor_id=actor.id,
            user_id=uuid.uuid4(),
            data=UserUpdateData(display_name="Whoever"),
            now=NOW,
            password_min_length=password_min_length,
        )


async def test_disabling_a_user_revokes_every_open_session_in_the_same_transaction(
    db_session: AsyncSession, password_min_length: int
) -> None:
    actor = await _create(
        db_session, role=AppUserRole.ADMIN, password_min_length=password_min_length
    )
    target = await _create(db_session, password_min_length=password_min_length)
    await sign_in(
        db_session,
        email=target.email,
        password=PASSWORD,
        now=NOW,
        token=b"\x09" * 32,
        max_failures=5,
        lock_minutes=15,
        session_ttl_hours=12,
    )

    await update_user(
        db_session,
        actor_id=actor.id,
        user_id=target.id,
        data=UserUpdateData(status=AppUserStatus.DISABLED),
        now=NOW,
        password_min_length=password_min_length,
    )

    session_row = (
        await db_session.execute(select(AuthSession).where(AuthSession.user_id == target.id))
    ).scalar_one()
    assert session_row.revoked_at == NOW


async def test_a_password_reset_changes_only_the_hash_and_keeps_sessions_and_lock(
    db_session: AsyncSession, password_min_length: int
) -> None:
    actor = await _create(
        db_session, role=AppUserRole.ADMIN, password_min_length=password_min_length
    )
    locked_until = datetime(2026, 6, 1, tzinfo=UTC)
    target = await _create(db_session, password_min_length=password_min_length)
    target.failed_logins = 3
    target.locked_until = locked_until
    db_session.add(
        AuthSession(
            user_id=target.id,
            token_hash="a" * 64,
            expires_at=NOW + timedelta(hours=12),
            revoked_at=None,
        )
    )
    await db_session.flush()
    target_id = target.id

    updated = await update_user(
        db_session,
        actor_id=actor.id,
        user_id=target_id,
        data=UserUpdateData(password="a-brand-new-password"),
        now=NOW,
        password_min_length=password_min_length,
    )

    assert verify_password("a-brand-new-password", updated.password_hash)
    assert updated.failed_logins == 3
    assert updated.locked_until == locked_until
    session_row = (
        await db_session.execute(select(AuthSession).where(AuthSession.user_id == target_id))
    ).scalar_one()
    assert session_row.revoked_at is None


async def test_user_updated_records_changed_fields_and_a_patch_that_changes_nothing_writes_no_row(
    db_session: AsyncSession, password_min_length: int
) -> None:
    actor = await _create(
        db_session, role=AppUserRole.ADMIN, password_min_length=password_min_length
    )
    target = await _create(
        db_session, display_name="Original Name", password_min_length=password_min_length
    )

    await update_user(
        db_session,
        actor_id=actor.id,
        user_id=target.id,
        data=UserUpdateData(display_name="Changed Name"),
        now=NOW,
        password_min_length=password_min_length,
    )
    row = (
        (
            await db_session.execute(
                text(
                    "SELECT payload FROM audit_event "
                    "WHERE entity_id = :id AND action = 'USER_UPDATED'"
                ),
                {"id": target.id},
            )
        )
        .mappings()
        .one()
    )
    assert row["payload"] == {"display_name": "Changed Name"}

    await update_user(
        db_session,
        actor_id=actor.id,
        user_id=target.id,
        data=UserUpdateData(display_name="Changed Name"),
        now=NOW,
        password_min_length=password_min_length,
    )
    count: int = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM audit_event WHERE entity_id = :id AND action = 'USER_UPDATED'"
            ),
            {"id": target.id},
        )
    ).scalar_one()
    assert count == 1


async def test_a_password_reset_writes_a_user_updated_row_with_password_mapped_to_null(
    db_session: AsyncSession, password_min_length: int
) -> None:
    actor = await _create(
        db_session, role=AppUserRole.ADMIN, password_min_length=password_min_length
    )
    target = await _create(db_session, password_min_length=password_min_length)

    await update_user(
        db_session,
        actor_id=actor.id,
        user_id=target.id,
        data=UserUpdateData(password="another-new-password"),
        now=NOW,
        password_min_length=password_min_length,
    )
    row = (
        (
            await db_session.execute(
                text(
                    "SELECT payload FROM audit_event "
                    "WHERE entity_id = :id AND action = 'USER_UPDATED'"
                ),
                {"id": target.id},
            )
        )
        .mappings()
        .one()
    )
    assert row["payload"] == {"password": None}
