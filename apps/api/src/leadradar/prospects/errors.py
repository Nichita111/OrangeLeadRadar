"""Typed errors of the [Prospects and evidence](/architecture/interfaces.md#prospects-and-evidence)
capability (`API-39` to `API-45`)."""

from __future__ import annotations

import uuid


class ProspectsError(Exception):
    """Base of every typed error this capability raises."""


class ProspectNotFound(ProspectsError):
    """No such account score, finding or override; `404 NOT_FOUND`."""


class OverrideRuleInvalid(ProspectsError):
    """`API-44`: `rule_key` names no rule of the service's active settings that currently matches
    for the account; `422 VALIDATION` naming `rule_key`."""


class OverrideConflict(ProspectsError):
    """`API-44` with an active override for the same rule, or `API-45` on an override already
    revoked; `409 CONFLICT` naming it."""

    def __init__(self, message: str, *, entity_id: uuid.UUID) -> None:
        super().__init__(message)
        self.entity_id = entity_id
