"""Integration tests of [`leadradar-seed-demo`](/architecture/overview.md#runtime) (the users
step, `S-RUN-03`, G2, G4)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.auth.errors import EmailTaken, PasswordTooShort
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import Service
from leadradar.db.models.identity import AppUser
from leadradar.seed.demo import (
    DemoAccountFileMissing,
    SeedSettings,
    seed_demo_accounts,
    seed_demo_industries,
    seed_demo_markets,
    seed_demo_services,
    seed_demo_source_plugins,
    seed_demo_users,
)

pytestmark = pytest.mark.integration

_DEMO_CSV = (
    "domain,name,country_code,industry\n"
    "lufthansagroup.com,Lufthansa Group,DE,AEROSPACE_AVIATION\n"
    "swiss.com,SWISS,CH,AEROSPACE_AVIATION\n"
)


async def _seed_full_dataset(
    db_session: AsyncSession, settings: SeedSettings, now: datetime
) -> None:
    admin_id = await seed_demo_users(db_session, settings)
    await seed_demo_industries(db_session, actor_id=admin_id, now=now)
    await seed_demo_markets(db_session, actor_id=admin_id, now=now)
    await seed_demo_source_plugins(db_session)
    await seed_demo_services(db_session, actor_id=admin_id, now=now)
    await seed_demo_accounts(db_session, settings=settings, actor_id=admin_id, now=now)


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


async def test_seed_demo_populates_services_and_accounts_once(
    db_session: AsyncSession, database_url: str, tmp_path: Path
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "demo_accounts.csv").write_text(_DEMO_CSV, encoding="utf-8")
    settings = _seed_settings(database_url, fixture_dir=fixture_dir)

    await _seed_full_dataset(db_session, settings, datetime.now(tz=UTC))

    services = (await db_session.execute(select(Service.code))).scalars().all()
    assert set(services) == {"INTELLIGENT_AUTOMATION", "CYBERSECURITY"}

    accounts = (await db_session.execute(select(Account.domain, Account.parent_account_id))).all()
    by_domain = {domain: parent_id for domain, parent_id in accounts}
    assert set(by_domain) == {"lufthansagroup.com", "swiss.com"}
    assert by_domain["swiss.com"] is not None
    assert by_domain["lufthansagroup.com"] is None


async def test_seed_demo_run_twice_fails_without_duplicating_services(
    db_session: AsyncSession, database_url: str, tmp_path: Path
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "demo_accounts.csv").write_text(_DEMO_CSV, encoding="utf-8")
    settings = _seed_settings(database_url, fixture_dir=fixture_dir)
    now = datetime.now(tz=UTC)

    await _seed_full_dataset(db_session, settings, now)
    service_count_before = (
        await db_session.execute(select(func.count()).select_from(Service))
    ).scalar_one()

    with pytest.raises((EmailTaken, IntegrityError)):
        await _seed_full_dataset(db_session, settings, now)

    service_count_after = (
        await db_session.execute(select(func.count()).select_from(Service))
    ).scalar_one()
    assert service_count_after == service_count_before


async def test_seed_demo_accounts_fails_clearly_without_the_demo_account_file(
    db_session: AsyncSession, database_url: str, tmp_path: Path
) -> None:
    settings = _seed_settings(database_url, fixture_dir=tmp_path / "no-fixtures-here")

    with pytest.raises(DemoAccountFileMissing):
        await seed_demo_accounts(
            db_session,
            settings=settings,
            actor_id=(await seed_demo_users(db_session, settings)),
            now=datetime.now(tz=UTC),
        )
