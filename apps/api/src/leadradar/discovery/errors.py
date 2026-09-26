"""Typed errors of the [Discovery](/architecture/interfaces.md#discovery) capability (`API-29` to
`API-32`), mapped once at the edge (`api/errors.py`)."""

from __future__ import annotations


class DiscoveryError(Exception):
    """Base of every typed error this capability raises."""


class CandidateNotFound(DiscoveryError):
    """`API-31`, `API-32`: no [`discovery_candidate`]
    (/architecture/sql-store.md#discovery_candidate) row has this id (`404 NOT_FOUND`)."""


class CandidateNotPending(DiscoveryError):
    """`API-31`, `API-32`: the candidate is already `ACCEPTED` or `REJECTED` ([Discovery
    contracts](/architecture/interfaces.md#discovery-contracts): "only a `PENDING` candidate can
    be decided", `409 CONFLICT`)."""


class CandidateDomainRequired(DiscoveryError):
    """`API-31`: the candidate has no domain and none was given ([Discovery]
    (/architecture/rules.md#discovery) Acceptance: "Accepting a candidate requires a domain",
    `422 VALIDATION` naming `field`)."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
