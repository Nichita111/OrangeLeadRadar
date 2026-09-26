"""Entry point `leadradar-seed-demo`: the users step of `make seed-demo`
([Seeding](/architecture/overview.md#runtime), [S-RUN-03](/requirements/system.md)). Loads the
two users of [Demo dataset](/architecture/overview.md#demo-dataset) Users into an empty
database, each through [`auth.users.create_user`](/architecture/services/api.md#design), so the
same password rule and `USER_CREATED` row apply as any other creation (G4). The rest of the demo
dataset (industries, markets, services, accounts) is a later task's; this is the smallest slice
`AC-52` and `AC-54` need.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.auth.users import UserCreateData, create_user
from leadradar.clock import build_clock
from leadradar.core.enums import AppUserRole
from leadradar.db.session import build_engine
from leadradar.logs import configure_json_logging
from leadradar.settings import ApiSettings

logger = logging.getLogger(__name__)


class SeedSettings(ApiSettings):
    """Adds the two demo passwords, required only by this entry point. `PASSWORD_MIN_LENGTH` is
    enforced once, by `auth.users.create_user` (`seed_demo_users` passes it through), not
    repeated here."""

    seed_admin_password: SecretStr
    seed_sales_password: SecretStr


# [Demo dataset](/architecture/overview.md#demo-dataset) Users: email, role, and the settings
# field holding its password. Display name is the email's local part (G2).
_DEMO_USERS = (
    ("admin@leadradar.local", AppUserRole.ADMIN, "seed_admin_password"),
    ("sales@leadradar.local", AppUserRole.SALES, "seed_sales_password"),
)


async def seed_demo_users(db: AsyncSession, settings: SeedSettings) -> None:
    """Creates the Admin and the Sales user of the demo dataset, with a null actor (seeding,
    G4)."""
    now = build_clock(settings)()
    for email, role, password_field in _DEMO_USERS:
        password = getattr(settings, password_field).get_secret_value()
        display_name = email.split("@", 1)[0]
        await create_user(
            db,
            actor_id=None,
            data=UserCreateData(
                email=email, display_name=display_name, role=role, password=password
            ),
            now=now,
            password_min_length=settings.password_min_length,
        )


async def _run(settings: SeedSettings) -> None:
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await seed_demo_users(db, settings)
    finally:
        await engine.dispose()


def run() -> None:
    """`leadradar-seed-demo`: fails loudly (a non-zero exit, one JSON log line) rather than
    seeding a partial or duplicate demo dataset."""
    settings = SeedSettings()
    configure_json_logging(settings.log_level)
    try:
        asyncio.run(_run(settings))
    except Exception:
        logger.exception("Seeding the demo users failed")
        sys.exit(1)
    logger.info("Seeded the demo users")


if __name__ == "__main__":
    run()
