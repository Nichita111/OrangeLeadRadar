"""The dependency every stub route carries, so a declared contract whose feature is not built
yet answers `501 NOT_IMPLEMENTED` before authentication and before its input is validated
([Conventions](/architecture/interfaces.md#conventions);
[api Design](/architecture/services/api.md#design))."""

from __future__ import annotations

from leadradar.api.errors import ContractNotBuilt


def contract_not_built() -> None:
    """Raises for every route whose feature is not built yet."""
    raise ContractNotBuilt
