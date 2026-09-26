"""Integration tests of [`leadradar-seed-demo`](/architecture/overview.md#runtime) (the users
step, `S-RUN-03`, G2, G4)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.auth.errors import EmailTaken, PasswordTooShort
from leadradar.db.models.identity import AppUser
from leadradar.seed.demo import SeedSettings, seed_demo_users

pytestmark = pytest.mark.integration


def _seed_settings(database_url: str, **overrides: Any) -> SeedSettings:
    defaults: dict[str, Any] = {
        "database_url": SecretStr(database_url),
        "migration_database_url": SecretStr(database_url),
        "seed_admin_password": SecretStr("a-strong-enough-admin-password"),
        "seed_sales_password": SecretStr("a-strong-enough-sales-password"),
    }
    defaults.update(overrides)
    return SeedSettings(**defaults)


async def test_seed_demo_creates_admin_and_sales_named_by_their_email_local_part(
    db_session: AsyncSession, database_url: str
) -> None:
    settings = _seed_settings(database_url)

    await seed_demo_users(db_session, settings)

    demo_emails = ("admin@leadradar.local", "sales@leadradar.local")
    users = (
        (
            await db_session.execute(
                select(AppUser).where(AppUser.email.in_(demo_emails)).order_by(AppUser.email)
            )
        )
        .scalars()
        .all()
    )
    by_email = {user.email: user for user in users}
    assert set(by_email) == set(demo_emails)
    assert by_email["admin@leadradar.local"].display_name == "admin"
    assert by_email["sales@leadradar.local"].display_name == "sales"

    rows = (
        await db_session.execute(
            text(
                "SELECT actor_id FROM audit_event WHERE action = 'USER_CREATED' "
                "AND entity_id = ANY(:ids)"
            ),
            {"ids": [user.id for user in users]},
        )
    ).all()
    assert len(rows) == 2
    for (actor_id,) in rows:
        assert actor_id is None


async def test_seed_demo_on_a_non_empty_database_fails_on_the_unique_email(
    db_session: AsyncSession, database_url: str
) -> None:
    settings = _seed_settings(database_url)
    await seed_demo_users(db_session, settings)

    with pytest.raises((EmailTaken, IntegrityError)):
        await seed_demo_users(db_session, settings)


def test_seed_demo_fails_without_seed_passwords(database_url: str) -> None:
    with pytest.raises(ValidationError):
        SeedSettings(
            database_url=SecretStr(database_url), migration_database_url=SecretStr(database_url)
        )


async def test_seed_demo_fails_with_a_seed_password_shorter_than_the_minimum(
    db_session: AsyncSession, database_url: str
) -> None:
    settings = _seed_settings(database_url, seed_admin_password=SecretStr("short"))
    with pytest.raises(PasswordTooShort):
        await seed_demo_users(db_session, settings)
