"""Pure rules of [`user_invite`](/architecture/sql-store.md#user_invite) (`S-SEC-05`)."""

from __future__ import annotations

from datetime import datetime, timedelta

from leadradar.core.sign_in import hash_session_token


def invite_expires_at(now: datetime, ttl_hours: int) -> datetime:
    """`expires_at`: creation time + `INVITE_TTL_HOURS`."""
    return now + timedelta(hours=ttl_hours)


def is_invite_pending(
    *,
    accepted_at: datetime | None,
    revoked_at: datetime | None,
    expires_at: datetime,
    now: datetime,
) -> bool:
    """Pending while neither accepted nor revoked and now is before `expires_at`."""
    return accepted_at is None and revoked_at is None and now < expires_at


def hash_invite_token(token: bytes) -> str:
    """The SHA-256 hex `token_hash` stores, as for a session token."""
    return hash_session_token(token)


def invite_link(app_base_url: str, token: bytes) -> str:
    """`APP_BASE_URL/invite#<token>`: the token rides in the fragment, which no request carries
    ([ADR-21](/architecture/adrs/adr-21-invite-links-and-the-invite-scene.md))."""
    return f"{app_base_url.rstrip('/')}/invite#{token.hex()}"
