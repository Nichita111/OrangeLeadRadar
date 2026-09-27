"""The `current_user` router dependency ([Conventions](/architecture/interfaces.md#conventions)
Authentication, G6 (a)): reads the session cookie and resolves it to the acting `Principal`
(`auth.sessions`). Plan task 2's `API-01` sets the cookie under `SESSION_COOKIE`; this module
adds no sign-in, sign-out, users route or role check."""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.auth.sessions import Principal, Unauthenticated, resolve_session
from leadradar.clock import now
from leadradar.db.session import get_session

SESSION_COOKIE = "leadradar_session"


async def current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Principal:
    """Raises `Unauthenticated` when the cookie is absent; otherwise resolves it in its own read
    transaction."""
    if session_token is None:
        raise Unauthenticated("No session cookie.")
    settings = request.app.state.settings
    current_time = now(fixture_mode=settings.fixture_mode, clock_file=settings.clock_file)
    return await resolve_session(session, session_token, current_time)


CurrentUser = Annotated[Principal, Depends(current_user)]
