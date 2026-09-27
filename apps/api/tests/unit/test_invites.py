"""Unit tests of the pure invite rules ([`user_invite`](/architecture/sql-store.md#user_invite),
`S-SEC-05`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from leadradar.core.invites import invite_expires_at, invite_link, is_invite_pending

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)


def test_an_invite_expires_ttl_hours_after_creation() -> None:
    assert invite_expires_at(NOW, 72) == NOW + timedelta(hours=72)


@pytest.mark.parametrize(
    ("accepted_at", "revoked_at", "expires_at", "pending"),
    [
        (None, None, NOW + timedelta(seconds=1), True),
        (NOW, None, NOW + timedelta(hours=1), False),
        (None, NOW, NOW + timedelta(hours=1), False),
        (None, None, NOW, False),
    ],
)
def test_pending_means_neither_used_nor_revoked_nor_expired(
    accepted_at: datetime | None, revoked_at: datetime | None, expires_at: datetime, pending: bool
) -> None:
    assert (
        is_invite_pending(
            accepted_at=accepted_at, revoked_at=revoked_at, expires_at=expires_at, now=NOW
        )
        is pending
    )


def test_the_link_carries_the_token_in_the_fragment() -> None:
    assert invite_link("http://localhost:8080/", b"\x01\xff") == "http://localhost:8080/invite#01ff"
