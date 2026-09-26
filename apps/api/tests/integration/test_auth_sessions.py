"""Integration tests of `auth.sessions.resolve_session`
([Conventions](/architecture/interfaces.md#conventions) Authentication,
[`auth_session`](/architecture/sql-store.md#auth_session))."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from leadradar.auth.sessions import Forbidden, Unauthenticated, hash_token, resolve_session
from leadradar.core.enums import AppUserRole, AppUserStatus
from leadradar.db.models.identity import AuthSession
from tests.integration import factories as f

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 15, tzinfo=UTC)
TOKEN = "a-plain-session-token"


async def _make_user_and_session(
    connection: AsyncConnection,
    *,
    user_status: AppUserStatus = AppUserStatus.ACTIVE,
    expires_at: datetime = NOW + timedelta(hours=1),
    revoked_at: datetime | None = None,
    token: str = TOKEN,
) -> uuid.UUID:
    def _insert(conn: Connection) -> uuid.UUID:
        user_id = f.make_app_user(
            conn, role=AppUserRole.SALES, status=user_status, display_name="Ada Lovelace"
        )
        f.make_auth_session(
            conn,
            user_id,
            token_hash=hash_token(token),
            expires_at=expires_at,
            revoked_at=revoked_at,
        )
        return user_id

    return await connection.run_sync(_insert)


async def test_resolves_the_principal_for_a_live_session(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    user_id = await _make_user_and_session(async_connection)

    principal = await resolve_session(async_session, TOKEN, NOW)

    assert principal.user_id == user_id
    assert principal.display_name == "Ada Lovelace"
    assert principal.role == AppUserRole.SALES


async def test_raises_unauthenticated_for_an_unknown_token(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    await _make_user_and_session(async_connection)

    with pytest.raises(Unauthenticated):
        await resolve_session(async_session, "not-the-right-token", NOW)


async def test_raises_unauthenticated_for_a_revoked_session(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    await _make_user_and_session(async_connection, revoked_at=NOW - timedelta(minutes=1))

    with pytest.raises(Unauthenticated):
        await resolve_session(async_session, TOKEN, NOW)


async def test_raises_unauthenticated_when_expires_at_equals_now(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    await _make_user_and_session(async_connection, expires_at=NOW)

    with pytest.raises(Unauthenticated):
        await resolve_session(async_session, TOKEN, NOW)


async def test_raises_unauthenticated_when_expires_at_is_earlier_than_now(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    await _make_user_and_session(async_connection, expires_at=NOW - timedelta(seconds=1))

    with pytest.raises(Unauthenticated):
        await resolve_session(async_session, TOKEN, NOW)


async def test_raises_forbidden_for_a_disabled_user(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    await _make_user_and_session(async_connection, user_status=AppUserStatus.DISABLED)

    with pytest.raises(Forbidden):
        await resolve_session(async_session, TOKEN, NOW)


async def test_the_session_table_holds_the_sha256_of_the_token_not_the_plain_token(
    async_connection: AsyncConnection,
) -> None:
    def _insert(conn: Connection) -> uuid.UUID:
        user_id = f.make_app_user(conn)
        return f.make_auth_session(conn, user_id, token_hash=hash_token(TOKEN))

    session_id = await async_connection.run_sync(_insert)

    stored_hash = await async_connection.scalar(
        select(AuthSession.token_hash).where(AuthSession.id == session_id)
    )
    assert stored_hash == hashlib.sha256(TOKEN.encode()).hexdigest()
    assert stored_hash != TOKEN


async def test_a_lookup_by_the_plain_token_finds_nothing(
    async_connection: AsyncConnection,
) -> None:
    def _insert(conn: Connection) -> None:
        user_id = f.make_app_user(conn)
        f.make_auth_session(conn, user_id, token_hash=hash_token(TOKEN))

    await async_connection.run_sync(_insert)

    found = await async_connection.scalar(
        select(AuthSession.id).where(AuthSession.token_hash == TOKEN)
    )
    assert found is None
