"""Password hashing ([api Design](/architecture/services/api.md#design) "Sessions and
passwords", [Python guidelines](/guidelines/python.md#style)): `argon2-cffi`'s `PasswordHasher`,
argon2id with its default parameters (G7). The plain password is never stored or logged."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """[`app_user`](/architecture/sql-store.md#app_user) `password_hash`."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True iff `password` matches `password_hash`; never raises on a mismatch."""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
