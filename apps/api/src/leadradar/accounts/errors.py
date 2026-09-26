"""Typed errors of the [Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts)
capability (its accounts half: `API-20` to `API-24`), mapped once at the edge
(`api/errors.py`)."""

from __future__ import annotations

import uuid


class AccountError(Exception):
    """Base of every typed error this capability raises."""


class AccountValidationError(AccountError):
    """The input is invalid; mapped to `422 VALIDATION` naming `field` in `details.fields[]`."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


class InvalidAccountDomain(AccountValidationError):
    """`domain` has no registrable domain ([Account identity]
    (/architecture/rules.md#account-identity), `API-21`, `API-22`)."""


class UnknownIndustry(AccountValidationError):
    """`industry` names no `ACTIVE` [`industry`](/architecture/sql-store.md#industry) code
    (`API-21`, `API-22`, `API-24`)."""


class UnknownParentAccount(AccountValidationError):
    """`parent_account_id` names no [`account`](/architecture/sql-store.md#account) (`API-21`,
    `API-24`)."""


class ImportTooLarge(AccountValidationError):
    """The uploaded file has more than `IMPORT_MAX_ROWS` rows (`API-22`, `S-ACC-02`)."""


class InvalidImportFile(AccountValidationError):
    """The uploaded file is not valid UTF-8 text ([`AccountImportRow`]
    (/architecture/interfaces.md#accountimportrow): "The file is UTF-8", `API-22`)."""


class DomainConflict(AccountError):
    """The domain already names an account; mapped to `409 CONFLICT` with
    `details.entity_id` (`API-21`)."""

    def __init__(self, existing_account_id: uuid.UUID, message: str) -> None:
        super().__init__(message)
        self.existing_account_id = existing_account_id


class AccountNotFound(AccountError):
    """No [`account`](/architecture/sql-store.md#account) row for the given id (`API-23`,
    `API-24`)."""
