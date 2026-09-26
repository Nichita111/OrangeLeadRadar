"""`API-59`'s push: a signed-in user pushes an account's current
[`account_score`](/architecture/sql-store.md#account_score) to the company
[`API-70`](/architecture/interfaces.md#crm) holds under the account's domain, and records the
outcome as one [`crm_sync`](/architecture/sql-store.md#crm_sync) row with a `CRM_PUSHED` audit
row ([Audit actions](/architecture/sql-store.md#audit-actions)), all in one transaction. The
token is checked before any read or outbound call, as the
[Outreach and CRM contracts](/architecture/interfaces.md#outreach-and-crm) `API-59` note states;
the outbound call happens between transactions, never inside an open one; a `FAILED` row is
committed even though the request then answers `503`
([Degradation](/architecture/overview.md#degradation))."""

from __future__ import annotations

import uuid
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.core.enums import AuditAction, CrmSyncStatus, CrmSyncTarget
from leadradar.db.models.identity import AppUser
from leadradar.db.models.outreach import CrmSync
from leadradar.outreach.company_push import (
    account_detail_url,
    build_company_push,
    top_signal_lines,
)
from leadradar.outreach.errors import CrmUnavailable, HubspotNotConfigured, ScoreNotFound
from leadradar.outreach.hubspot import upsert_company
from leadradar.outreach.queries import CrmSyncResult, read_push_inputs
from leadradar.settings import ApiSettings


async def _record_crm_sync(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    score_id: uuid.UUID,
    status: CrmSyncStatus,
    external_id: str | None,
    error: str | None,
    requested_by: uuid.UUID,
    occurred_at: datetime,
) -> CrmSync:
    """Adds a [`crm_sync`](/architecture/sql-store.md#crm_sync) row and its `CRM_PUSHED` audit row
    ([Audit actions](/architecture/sql-store.md#audit-actions)) to `session`; does not commit. The
    caller opens and commits the surrounding transaction."""
    crm_sync = CrmSync(
        account_id=account_id,
        service_id=service_id,
        score_id=score_id,
        target=CrmSyncTarget.HUBSPOT,
        external_id=external_id,
        status=status,
        error=error,
        requested_by=requested_by,
    )
    session.add(crm_sync)
    await session.flush()
    await append_audit_event(
        session,
        occurred_at=occurred_at,
        actor_id=requested_by,
        action=AuditAction.CRM_PUSHED,
        entity_type="crm_sync",
        entity_id=crm_sync.id,
        payload={"target": CrmSyncTarget.HUBSPOT.value, "status": status.value},
    )
    return crm_sync


async def push_to_crm(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    principal: AppUser,
    settings: ApiSettings,
    http: httpx.AsyncClient,
    now: datetime,
) -> CrmSyncResult:
    """`API-59`. Raises `HubspotNotConfigured` when `HUBSPOT_ACCESS_TOKEN` is unset, before any
    read; `ScoreNotFound` when the account has no current score for the service; re-raises
    `CrmUnavailable` after committing the `FAILED` row."""
    if settings.hubspot_access_token is None:
        raise HubspotNotConfigured("HUBSPOT_ACCESS_TOKEN is not set.")

    # Its own transaction, committed before the outbound call: a read writes nothing, and
    # `session.begin()` below (the write) must not open onto an already-begun transaction.
    async with session.begin():
        inputs = await read_push_inputs(
            session, account_id, service_id, settings.hubspot_top_signals
        )
    if inputs is None:
        raise ScoreNotFound(f"No current score for account {account_id}, service {service_id}.")

    push = build_company_push(
        domain=inputs.account_domain,
        name=inputs.account_name,
        service_name=inputs.service_name,
        priority=inputs.priority,
        band=inputs.band,
        standing=inputs.standing,
        signal_lines=top_signal_lines(inputs.top_signals),
        account_url=account_detail_url(settings.app_base_url, account_id),
    )

    try:
        external_id = await upsert_company(
            http,
            settings.hubspot_access_token.get_secret_value(),
            push,
            settings.hubspot_timeout_s,
        )
    except CrmUnavailable as exc:
        async with session.begin():
            await _record_crm_sync(
                session,
                account_id=account_id,
                service_id=service_id,
                score_id=inputs.score_id,
                status=CrmSyncStatus.FAILED,
                external_id=None,
                error=str(exc),
                requested_by=principal.id,
                occurred_at=now,
            )
        raise

    async with session.begin():
        crm_sync = await _record_crm_sync(
            session,
            account_id=account_id,
            service_id=service_id,
            score_id=inputs.score_id,
            status=CrmSyncStatus.SUCCEEDED,
            external_id=external_id,
            error=None,
            requested_by=principal.id,
            occurred_at=now,
        )

    return CrmSyncResult(
        id=crm_sync.id,
        external_id=crm_sync.external_id,
        error=crm_sync.error,
        created_at=crm_sync.created_at,
        target=crm_sync.target,
        status=crm_sync.status,
    )
