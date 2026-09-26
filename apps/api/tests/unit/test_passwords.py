"""Unit test of [`auth/passwords.py`](/guidelines/python.md#style): argon2id, default
parameters (G7), [N-07](/requirements/system.md)."""

from __future__ import annotations

import pytest

from leadradar.auth.passwords import hash_password, verify_password

pytestmark = pytest.mark.unit


def test_password_hash_is_argon2id_and_verifies_only_the_right_password() -> None:
    password_hash = hash_password("a-strong-enough-password")

    assert password_hash.startswith("$argon2id$")
    assert verify_password("a-strong-enough-password", password_hash)
    assert not verify_password("the-wrong-password", password_hash)
