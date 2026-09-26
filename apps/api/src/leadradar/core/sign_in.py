"""Pure rules of sign-in, sessions and user changes ([S-SEC-01](/requirements/system.md),
[S-SEC-03](/requirements/system.md)).

Every function here takes "now" as an argument and touches no store: the capability functions
of `auth/` load the current state, call these, and write the result.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from leadradar.core.enums import AppUserRole, AppUserStatus


class SignInOutcome(StrEnum):
    """The result `decide_sign_in` reaches; `API-01`'s note."""

    SUCCEEDED = "SUCCEEDED"
    BAD_CREDENTIALS = "BAD_CREDENTIALS"
    LOCKED = "LOCKED"
    DISABLED = "DISABLED"


class LoginFailedReason(StrEnum):
    """`audit_event.payload.reason` on a `LOGIN_FAILED` row, the closed set
    [Audit actions](/architecture/sql-store.md#audit-actions) `LOGIN_FAILED` states."""

    BAD_CREDENTIALS = "BAD_CREDENTIALS"
    LOCKED = "LOCKED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class UserAuthState:
    """The [`app_user`](/architecture/sql-store.md#app_user) columns `decide_sign_in` reads."""

    status: AppUserStatus
    failed_logins: int
    locked_until: datetime | None


@dataclass(frozen=True)
class SignInDecision:
    """What `decide_sign_in` answers: the outcome, the new counters to write, and the audit
    `LOGIN_FAILED` `reason` ([Audit actions](/architecture/sql-store.md#audit-actions)), null on
    a success."""

    outcome: SignInOutcome
    failed_logins: int
    locked_until: datetime | None
    reason: LoginFailedReason | None
    retry_after_min: int | None


def retry_after_min(now: datetime, locked_until: datetime) -> int:
    """Minutes from `now` to `locked_until`, rounded up (G3)."""
    seconds = (locked_until - now).total_seconds()
    return math.ceil(seconds / 60)


def decide_sign_in(
    user_state: UserAuthState,
    password_matches: bool,
    now: datetime,
    max_failures: int,
    lock_minutes: int,
) -> SignInDecision:
    """`API-01`'s note and G3, G4: locked (regardless of the password) beats a wrong password,
    which beats a disabled account, which beats success."""
    if user_state.locked_until is not None and now < user_state.locked_until:
        return SignInDecision(
            outcome=SignInOutcome.LOCKED,
            failed_logins=user_state.failed_logins,
            locked_until=user_state.locked_until,
            reason=LoginFailedReason.LOCKED,
            retry_after_min=retry_after_min(now, user_state.locked_until),
        )

    if not password_matches:
        failed_logins = user_state.failed_logins + 1
        if failed_logins >= max_failures:
            locked_until = now + timedelta(minutes=lock_minutes)
            return SignInDecision(
                outcome=SignInOutcome.LOCKED,
                failed_logins=0,
                locked_until=locked_until,
                reason=LoginFailedReason.BAD_CREDENTIALS,
                retry_after_min=retry_after_min(now, locked_until),
            )
        return SignInDecision(
            outcome=SignInOutcome.BAD_CREDENTIALS,
            failed_logins=failed_logins,
            locked_until=user_state.locked_until,
            reason=LoginFailedReason.BAD_CREDENTIALS,
            retry_after_min=None,
        )

    if user_state.status == AppUserStatus.DISABLED:
        return SignInDecision(
            outcome=SignInOutcome.DISABLED,
            failed_logins=user_state.failed_logins,
            locked_until=user_state.locked_until,
            reason=LoginFailedReason.DISABLED,
            retry_after_min=None,
        )

    return SignInDecision(
        outcome=SignInOutcome.SUCCEEDED,
        failed_logins=0,
        locked_until=user_state.locked_until,
        reason=None,
        retry_after_min=None,
    )


def session_expires_at(now: datetime, ttl_hours: int) -> datetime:
    """[`auth_session`](/architecture/sql-store.md#auth_session) `expires_at`."""
    return now + timedelta(hours=ttl_hours)


def is_session_valid(expires_at: datetime, revoked_at: datetime | None, now: datetime) -> bool:
    """True iff the session is not revoked and not yet expired at `now`."""
    return revoked_at is None and now < expires_at


def hash_session_token(token: bytes) -> str:
    """The SHA-256 hex of the session token, the only form [`auth_session`](
    /architecture/sql-store.md#auth_session) `token_hash` stores (api Design "Sessions and
    passwords")."""
    return hashlib.sha256(token).hexdigest()


def refuse_self_change(
    actor_id: uuid.UUID,
    target_id: uuid.UUID,
    update: Mapping[str, object],
    current_role: AppUserRole,
) -> bool:
    """True when the change must be refused (`409 CONFLICT`): an Admin sending a different role
    or `DISABLED` for themselves (`API-06`'s note, `S-SEC-03`). Sending one's current role is not
    a change and is not refused."""
    if actor_id != target_id:
        return False
    if "role" in update and update["role"] != current_role:
        return True
    return update.get("status") == AppUserStatus.DISABLED


def changed_fields(
    current: Mapping[str, object], update: Mapping[str, object]
) -> dict[str, object]:
    """Maps each field of `update` that differs from `current` to its new value; `password`
    always maps to null when sent, so a reset is recorded without its value (G4). Empty when
    nothing in `update` differs from `current` (G8)."""
    result: dict[str, object] = {}
    for field, value in update.items():
        if field == "password":
            result[field] = None
            continue
        if current.get(field) != value:
            result[field] = value
    return result
