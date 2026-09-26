"""Typed errors of the "auth and users" capability, mapped once at the edge by
[`api/errors.py`](../api/errors.py) onto the envelope of
[Conventions](/architecture/interfaces.md#conventions)."""

from __future__ import annotations

import uuid


class Unauthenticated(Exception):
    """No valid session (`current_user`); `UNAUTHENTICATED`."""


class InvalidCredentials(Exception):
    """Wrong email or password at `API-01`; the same `401` message as `Unauthenticated`, so a
    caller cannot tell which was wrong."""


class AccountLocked(Exception):
    """Too many failed sign-ins (`API-01`'s note); `423 LOCKED`."""

    def __init__(self, retry_after_min: int) -> None:
        super().__init__("Account locked")
        self.retry_after_min = retry_after_min


class AccountDisabled(Exception):
    """The right password on a `DISABLED` account (`API-01`'s note); `403 FORBIDDEN`."""


class Forbidden(Exception):
    """A signed-in user without the role a route needs (`require_admin`); `403 FORBIDDEN`."""


class UserNotFound(Exception):
    """`API-06` on an unknown `id`; `404`."""


class EmailTaken(Exception):
    """`API-05` with an email that already exists, case-insensitively; `409 CONFLICT` naming the
    existing user."""

    def __init__(self, entity_id: uuid.UUID) -> None:
        super().__init__("Email already in use")
        self.entity_id = entity_id


class SelfChangeRefused(Exception):
    """An Admin trying to change their own role or disable themselves (`API-06`'s note,
    `S-SEC-03`); `409 CONFLICT`."""


class PasswordTooShort(Exception):
    """A `password` shorter than `PASSWORD_MIN_LENGTH` at `create_user` or `update_user`
    ([`UserCreate`](/architecture/interfaces.md#usercreate) and
    [`UserUpdate`](/architecture/interfaces.md#userupdate) `password`); `422 VALIDATION`. The one
    place the rule is enforced, so every caller — `API-05`, `API-06` and the seed — shares it."""

    def __init__(self, minimum: int) -> None:
        super().__init__(f"password must be at least {minimum} characters")
        self.minimum = minimum
