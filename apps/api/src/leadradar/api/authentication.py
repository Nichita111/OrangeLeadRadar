"""Authentication and role dependencies ([Conventions](/architecture/interfaces.md#conventions)
Roles and Authentication, `S-SEC-02`): every route but `API-01` and `API-61` declares
`current_user` or `require_admin`."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.auth.errors import Forbidden, Unauthenticated
from leadradar.auth.sessions import authenticate
from leadradar.core.enums import AppUserRole
from leadradar.db.models.identity import AppUser

SESSION_COOKIE_NAME = "leadradar_session"


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One `AsyncSession` per request; the capability function it is passed to opens and
    commits its own transaction (api Design "Transactions")."""
    async with AsyncSession(request.app.state.engine, expire_on_commit=False) as session:
        yield session


async def current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> AppUser:
    """Reads the session cookie, hashes the token and loads the session it names; raises
    `Unauthenticated` when there is none, an unreadable one, or an expired or revoked one."""
    if session_cookie is None:
        raise Unauthenticated
    try:
        token = bytes.fromhex(session_cookie)
    except ValueError:
        raise Unauthenticated from None
    now = request.app.state.clock()
    return await authenticate(db, token=token, now=now)


async def require_admin(user: AppUser = Depends(current_user)) -> AppUser:
    """Builds on `current_user`: a role other than `ADMIN` raises `Forbidden`."""
    if user.role is not AppUserRole.ADMIN:
        raise Forbidden
    return user
