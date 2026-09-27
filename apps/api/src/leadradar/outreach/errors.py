"""Typed errors of the [Outreach and CRM](/architecture/interfaces.md#outreach-and-crm)
`API-56` to `API-59` capability, mapped once at the edge (`api/errors.py`) onto the envelope."""

from __future__ import annotations


class OutreachError(Exception):
    """Base of every typed error this capability raises."""


class HubspotNotConfigured(OutreachError):
    """`HUBSPOT_ACCESS_TOKEN` is unset: `API-59` answers `409 NOT_CONFIGURED` and writes nothing,
    per [Outreach and CRM](/architecture/interfaces.md#outreach-and-crm)."""


class ScoreNotFound(OutreachError):
    """No current [`account_score`](/architecture/sql-store.md#account_score) for the account
    and service (`API-59`)."""


class CrmUnavailable(OutreachError):
    """[`API-70`](/architecture/interfaces.md#crm) failed: a transport error, a timeout, or any
    non-2xx HubSpot answer, including a portal missing the `leadradar_*` properties
    ([Degradation](/architecture/overview.md#degradation))."""


class OutreachNotFound(OutreachError):
    """The account, service or [`outreach_draft`](/architecture/sql-store.md#outreach_draft) a
    draft request names does not exist (`API-56` to `API-58`); mapped to `404`."""


class OutreachValidationError(OutreachError):
    """The request is invalid (`API-56`, `API-58`): a contact of another account, a subject on
    an InMail, a status move other than to `EXPORTED`, or an account without an in-force
    positive finding for the service ([Outreach grounding]
    (/architecture/rules.md#outreach-grounding)); mapped to `422 VALIDATION` naming `field`."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
