"""Unit tests of [`core/sign_in.py`](/architecture/services/api.md#design) ("Sessions and
passwords"): the pure sign-in decision, session validity and the self-change and changed-fields
rules of `S-SEC-01`, `S-SEC-03` and G3, G4, G8."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from leadradar.core.enums import AppUserRole, AppUserStatus
from leadradar.core.sign_in import (
    SignInOutcome,
    UserAuthState,
    changed_fields,
    decide_sign_in,
    hash_session_token,
    is_session_valid,
    refuse_self_change,
    retry_after_min,
    session_expires_at,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 1, tzinfo=UTC)
MAX_FAILURES = 5
LOCK_MINUTES = 15


def _state(**overrides: Any) -> UserAuthState:
    defaults: dict[str, Any] = {
        "status": AppUserStatus.ACTIVE,
        "failed_logins": 0,
        "locked_until": None,
    }
    defaults.update(overrides)
    return UserAuthState(**defaults)


def test_failures_below_the_maximum_answer_bad_credentials_and_count_up() -> None:
    decision = decide_sign_in(
        _state(failed_logins=MAX_FAILURES - 2),
        password_matches=False,
        now=NOW,
        max_failures=MAX_FAILURES,
        lock_minutes=LOCK_MINUTES,
    )
    assert decision.outcome == SignInOutcome.BAD_CREDENTIALS
    assert decision.failed_logins == MAX_FAILURES - 1
    assert decision.locked_until is None
    assert decision.reason == "BAD_CREDENTIALS"


def test_the_failure_reaching_the_maximum_locks_resets_the_count_and_records_bad_credentials() -> (
    None
):
    decision = decide_sign_in(
        _state(failed_logins=MAX_FAILURES - 1),
        password_matches=False,
        now=NOW,
        max_failures=MAX_FAILURES,
        lock_minutes=LOCK_MINUTES,
    )
    assert decision.outcome == SignInOutcome.LOCKED
    assert decision.failed_logins == 0
    assert decision.locked_until == NOW + timedelta(minutes=LOCK_MINUTES)
    assert decision.reason == "BAD_CREDENTIALS"
    assert decision.retry_after_min == LOCK_MINUTES


def test_an_attempt_while_locked_answers_locked_with_reason_locked_even_when_right() -> None:
    locked_until = NOW + timedelta(minutes=5)
    decision = decide_sign_in(
        _state(locked_until=locked_until),
        password_matches=True,
        now=NOW,
        max_failures=MAX_FAILURES,
        lock_minutes=LOCK_MINUTES,
    )
    assert decision.outcome == SignInOutcome.LOCKED
    assert decision.reason == "LOCKED"
    assert decision.retry_after_min == 5


def test_the_lock_ends_exactly_at_locked_until() -> None:
    locked_until = NOW + timedelta(minutes=5)
    still_locked = decide_sign_in(
        _state(locked_until=locked_until),
        password_matches=True,
        now=locked_until - timedelta(seconds=1),
        max_failures=MAX_FAILURES,
        lock_minutes=LOCK_MINUTES,
    )
    assert still_locked.outcome == SignInOutcome.LOCKED

    no_longer_locked = decide_sign_in(
        _state(locked_until=locked_until),
        password_matches=True,
        now=locked_until,
        max_failures=MAX_FAILURES,
        lock_minutes=LOCK_MINUTES,
    )
    assert no_longer_locked.outcome == SignInOutcome.SUCCEEDED


def test_after_a_lock_expires_one_failure_counts_one_and_does_not_relock() -> None:
    past_lock = NOW - timedelta(minutes=1)
    decision = decide_sign_in(
        _state(failed_logins=0, locked_until=past_lock),
        password_matches=False,
        now=NOW,
        max_failures=MAX_FAILURES,
        lock_minutes=LOCK_MINUTES,
    )
    assert decision.outcome == SignInOutcome.BAD_CREDENTIALS
    assert decision.failed_logins == 1
    assert decision.locked_until == past_lock


@pytest.mark.parametrize(
    ("remaining", "expected"),
    [
        (timedelta(minutes=15), 15),
        (timedelta(minutes=14, seconds=1), 15),
        (timedelta(seconds=30), 1),
    ],
)
def test_retry_after_min_rounds_up_the_remaining_time(remaining: timedelta, expected: int) -> None:
    assert retry_after_min(NOW, NOW + remaining) == expected


def test_a_success_resets_the_failure_count() -> None:
    decision = decide_sign_in(
        _state(failed_logins=3),
        password_matches=True,
        now=NOW,
        max_failures=MAX_FAILURES,
        lock_minutes=LOCK_MINUTES,
    )
    assert decision.outcome == SignInOutcome.SUCCEEDED
    assert decision.failed_logins == 0


def test_right_password_on_disabled_answers_disabled_wrong_password_answers_bad_credentials() -> (
    None
):
    disabled = _state(status=AppUserStatus.DISABLED)

    right_password = decide_sign_in(
        disabled,
        password_matches=True,
        now=NOW,
        max_failures=MAX_FAILURES,
        lock_minutes=LOCK_MINUTES,
    )
    assert right_password.outcome == SignInOutcome.DISABLED

    wrong_password = decide_sign_in(
        disabled,
        password_matches=False,
        now=NOW,
        max_failures=MAX_FAILURES,
        lock_minutes=LOCK_MINUTES,
    )
    assert wrong_password.outcome == SignInOutcome.BAD_CREDENTIALS


def test_session_expires_ttl_hours_after_creation() -> None:
    assert session_expires_at(NOW, 12) == NOW + timedelta(hours=12)


def test_session_is_invalid_at_expiry_and_after_revocation() -> None:
    expires_at = NOW + timedelta(hours=12)
    assert is_session_valid(expires_at, revoked_at=None, now=expires_at - timedelta(seconds=1))
    assert not is_session_valid(expires_at, revoked_at=None, now=expires_at)
    assert not is_session_valid(expires_at, revoked_at=NOW, now=NOW - timedelta(seconds=1))


def test_session_token_hash_is_the_sha256_hex_and_never_the_token() -> None:
    token = b"\x00" * 32
    hashed = hash_session_token(token)
    assert hashed == hashlib.sha256(token).hexdigest()
    assert token.hex() not in hashed


def test_admin_cannot_change_own_role_or_disable_self_but_may_change_own_name_and_password() -> (
    None
):
    admin_id = uuid.uuid4()
    assert refuse_self_change(
        admin_id, admin_id, {"role": AppUserRole.SALES}, current_role=AppUserRole.ADMIN
    )
    assert refuse_self_change(
        admin_id, admin_id, {"status": AppUserStatus.DISABLED}, current_role=AppUserRole.ADMIN
    )
    assert not refuse_self_change(
        admin_id,
        admin_id,
        {"display_name": "New Name", "password": "irrelevant-but-long-enough"},
        current_role=AppUserRole.ADMIN,
    )


def test_sending_ones_current_role_is_not_a_change() -> None:
    admin_id = uuid.uuid4()
    assert not refuse_self_change(
        admin_id, admin_id, {"role": AppUserRole.ADMIN}, current_role=AppUserRole.ADMIN
    )


def test_admin_may_demote_and_disable_another_admin() -> None:
    actor_id, other_admin_id = uuid.uuid4(), uuid.uuid4()
    assert not refuse_self_change(
        actor_id, other_admin_id, {"role": AppUserRole.SALES}, current_role=AppUserRole.ADMIN
    )
    assert not refuse_self_change(
        actor_id,
        other_admin_id,
        {"status": AppUserStatus.DISABLED},
        current_role=AppUserRole.ADMIN,
    )


def test_changed_fields_maps_each_changed_field_to_its_new_value_and_password_to_null() -> None:
    current = {"display_name": "Old", "role": AppUserRole.SALES, "status": AppUserStatus.ACTIVE}
    update = {"display_name": "New", "password": "a-new-password"}
    assert changed_fields(current, update) == {"display_name": "New", "password": None}


def test_changed_fields_is_empty_when_every_sent_value_equals_the_current_one() -> None:
    current = {"display_name": "Same", "role": AppUserRole.SALES}
    update = {"display_name": "Same", "role": AppUserRole.SALES}
    assert changed_fields(current, update) == {}
