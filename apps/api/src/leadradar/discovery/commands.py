"""The api's discovery commands ([Discovery contracts]
(/architecture/interfaces.md#discovery-contracts)): `API-29` requests a discovery run, `API-31`
and `API-32` decide a candidate. Each commits the request's one transaction — the one its
authentication opened — writing the change and its audit row together, as
[`runs.commands`](../runs/commands.py) does."""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.commands import create_discovered_account
from leadradar.accounts.queries import AccountData, account_data
from leadradar.audit.events import append_audit_event
from leadradar.configuration.queries import require_service
from leadradar.core.enums import (
    AuditAction,
    DiscoveryCandidateStatus,
    PipelineRunKind,
    PipelineRunTrigger,
    SourcePluginCode,
)
from leadradar.db.models.accounts import DiscoveryCandidate
from leadradar.db.models.identity import AppUser
from leadradar.discovery.errors import (
    CandidateDomainRequired,
    CandidateNotFound,
    CandidateNotPending,
)
from leadradar.discovery.queries import DiscoveryCandidateView, get_candidate
from leadradar.runs.enqueue import enqueue_account_refresh, enqueue_service_discovery
from leadradar.runs.errors import RunNotFound
from leadradar.runs.queries import RunView, available_refresh_plugins, read_run


@dataclass(frozen=True)
class DiscoveryRunRequested:
    """`API-29`'s result: the run, and whether this request created it (`202`) or found it
    queued or running (`200`)."""

    run: RunView
    created: bool


async def request_discovery_run(
    session: AsyncSession, *, service_id: uuid.UUID, principal: AppUser, now: datetime
) -> DiscoveryRunRequested:
    """`API-29`: enqueues a `USER` discovery run of the service with its `RUN_REQUESTED` audit
    row, or returns the one already queued or running. Raises `ServiceNotFound`."""
    await require_service(session, service_id)

    run_id, created = await enqueue_service_discovery(
        session, service_id=service_id, requested_by=principal.id, now=now
    )
    if created:
        await append_audit_event(
            session,
            action=AuditAction.RUN_REQUESTED,
            occurred_at=now,
            actor_id=principal.id,
            entity_type="pipeline_run",
            entity_id=run_id,
            payload={
                "kind": PipelineRunKind.DISCOVERY.value,
                "trigger": PipelineRunTrigger.USER.value,
            },
            run_id=run_id,
        )
    view = await read_run(session, run_id)
    await session.commit()
    if view is None:
        raise RunNotFound(f"No run {run_id}.")
    return DiscoveryRunRequested(run=view, created=created)


async def _load_pending_candidate(
    session: AsyncSession, candidate_id: uuid.UUID
) -> DiscoveryCandidate:
    candidate = (
        await session.execute(
            select(DiscoveryCandidate)
            .where(DiscoveryCandidate.id == candidate_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise CandidateNotFound(f"No discovery candidate {candidate_id}.")
    if candidate.status != DiscoveryCandidateStatus.PENDING:
        raise CandidateNotPending(f"Candidate {candidate_id} is already {candidate.status}.")
    return candidate


async def accept_candidate(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    domain: str | None,
    keys_configured: Collection[SourcePluginCode],
    principal: AppUser,
    now: datetime,
) -> AccountData:
    """`API-31`, `S-DSC-02`: creates the account (`leadradar.accounts.commands
    .create_discovered_account`), links the candidate, queues its refresh, and writes
    `CANDIDATE_ACCEPTED`. Raises `CandidateNotFound`, `CandidateNotPending`,
    `CandidateDomainRequired`, or `create_discovered_account`'s own errors."""
    candidate = await _load_pending_candidate(session, candidate_id)

    resolved_domain = candidate.domain or domain
    if not resolved_domain:
        raise CandidateDomainRequired("domain", "A domain is required to accept this candidate.")

    account = await create_discovered_account(
        session,
        domain=resolved_domain,
        name=candidate.name,
        country_code=candidate.country_code,
        industry=candidate.industry,
        employee_count=candidate.employee_count,
        actor_id=principal.id,
        now=now,
    )

    candidate.status = DiscoveryCandidateStatus.ACCEPTED
    candidate.decided_by = principal.id
    candidate.decided_at = now
    candidate.account_id = account.id

    await append_audit_event(
        session,
        action=AuditAction.CANDIDATE_ACCEPTED,
        occurred_at=now,
        actor_id=principal.id,
        entity_type="discovery_candidate",
        entity_id=candidate.id,
        payload={"account_id": str(account.id)},
    )

    await enqueue_account_refresh(
        session,
        account_id=account.id,
        trigger=PipelineRunTrigger.USER,
        requested_by=principal.id,
        available_plugins=await available_refresh_plugins(
            session, keys_configured=keys_configured, now=now
        ),
        now=now,
    )

    result = await account_data(session, account)
    await session.commit()
    return result


async def reject_candidate(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    reason: str | None,
    principal: AppUser,
    now: datetime,
) -> DiscoveryCandidateView:
    """`API-32`, `S-DSC-02`: removes the candidate from the pending list for good and writes
    `CANDIDATE_REJECTED`. Raises `CandidateNotFound`, `CandidateNotPending`."""
    candidate = await _load_pending_candidate(session, candidate_id)

    candidate.status = DiscoveryCandidateStatus.REJECTED
    candidate.decided_by = principal.id
    candidate.decided_at = now
    candidate.reject_reason = reason

    await append_audit_event(
        session,
        action=AuditAction.CANDIDATE_REJECTED,
        occurred_at=now,
        actor_id=principal.id,
        entity_type="discovery_candidate",
        entity_id=candidate.id,
        payload={"reason": reason},
    )
    await session.commit()
    return await get_candidate(session, candidate_id)
