"""Integration tests of [`discovery.commands`](/architecture/rules.md#discovery) (`API-29`,
`API-31`, `API-32`, `S-DSC-01`, `S-DSC-02`) against a real database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AppUserRole,
    AppUserStatus,
    AuditAction,
    DiscoveryCandidateOrigin,
    DiscoveryCandidateStatus,
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
    ScoringConfigStatus,
    ServiceStatus,
)
from leadradar.db.models.accounts import Account, DiscoveryCandidate
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.configuration import ScoringConfig, Service
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.discovery.commands import accept_candidate, reject_candidate, request_discovery_run
from leadradar.discovery.errors import (
    CandidateDomainRequired,
    CandidateNotFound,
    CandidateNotPending,
    NoActiveScoringVersion,
    ServiceNotActive,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 15, tzinfo=UTC)


async def _make_actor(session: AsyncSession) -> AppUser:
    user = AppUser(
        email=f"user-{uuid.uuid4()}@example.com",
        display_name="Test User",
        role=AppUserRole.SALES,
        status=AppUserStatus.ACTIVE,
        password_hash="hash",
        failed_logins=0,
        locked_until=None,
        last_login_at=None,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_service(
    session: AsyncSession,
    *,
    active_version: bool = True,
    status: ServiceStatus = ServiceStatus.ACTIVE,
) -> uuid.UUID:
    unique = uuid.uuid4().hex[:8].upper()
    service = Service(
        code=f"SERVICE_{unique}",
        name=f"Service {unique}",
        description="A service.",
        value_proposition="A value proposition.",
        status=status,
    )
    session.add(service)
    await session.flush()
    if active_version:
        session.add(
            ScoringConfig(
                service_id=service.id,
                version=1,
                status=ScoringConfigStatus.ACTIVE,
                settings={},
                change_note=None,
                activated_at=NOW,
                activated_by=None,
            )
        )
        await session.flush()
    return service.id


async def _make_candidate(
    session: AsyncSession, *, service_id: uuid.UUID, run_id: uuid.UUID, **overrides: object
) -> DiscoveryCandidate:
    defaults: dict[str, object] = {
        "service_id": service_id,
        "run_id": run_id,
        "name": "Lufthansa",
        "normalised_name": "lufthansa",
        "domain": None,
        "country_code": "DE",
        "industry": None,
        "employee_count": None,
        "origin": DiscoveryCandidateOrigin.NEWS_MENTION,
        "document_id": None,
        "quote": None,
        "fit_estimate": 63,
        "status": DiscoveryCandidateStatus.PENDING,
        "decided_by": None,
        "decided_at": None,
        "reject_reason": None,
        "account_id": None,
    }
    defaults.update(overrides)
    candidate = DiscoveryCandidate(**defaults)
    session.add(candidate)
    await session.flush()
    return candidate


async def _make_run(session: AsyncSession, *, service_id: uuid.UUID) -> uuid.UUID:
    run = PipelineRun(
        kind=PipelineRunKind.DISCOVERY,
        trigger=PipelineRunTrigger.USER,
        account_id=None,
        service_id=service_id,
        question_id=None,
        status=PipelineRunStatus.SUCCEEDED,
        stage=None,
        progress={},
        errors=[],
        requested_by=None,
        started_at=NOW,
        finished_at=NOW,
    )
    session.add(run)
    await session.flush()
    return run.id


# --- request_discovery_run (API-29, G7) -----------------------------------------------------


async def test_request_discovery_run_enqueues_one_discover_job(db_session: AsyncSession) -> None:
    service_id = await _make_service(db_session)
    actor = await _make_actor(db_session)

    result = await request_discovery_run(
        db_session, service_id=service_id, principal=actor, now=NOW
    )

    assert result.created
    jobs = (
        (await db_session.execute(select(Job).where(Job.run_id == result.run.id))).scalars().all()
    )
    assert [job.step for job in jobs] == [JobStep.DISCOVER]
    assert jobs[0].status == JobStatus.READY
    audit = (
        await db_session.execute(
            select(AuditEvent).where(AuditEvent.action == AuditAction.RUN_REQUESTED)
        )
    ).scalar_one()
    assert audit.entity_id == result.run.id


async def test_a_second_request_returns_the_queued_run(db_session: AsyncSession) -> None:
    service_id = await _make_service(db_session)
    actor = await _make_actor(db_session)

    first = await request_discovery_run(db_session, service_id=service_id, principal=actor, now=NOW)
    second = await request_discovery_run(
        db_session, service_id=service_id, principal=actor, now=NOW
    )

    assert second.created is False
    assert second.run.id == first.run.id
    assert (
        await db_session.execute(select(func.count()).select_from(PipelineRun))
    ).scalar_one() == 1


async def test_an_inactive_service_raises_service_not_active(db_session: AsyncSession) -> None:
    service_id = await _make_service(db_session, status=ServiceStatus.INACTIVE)
    actor = await _make_actor(db_session)

    with pytest.raises(ServiceNotActive):
        await request_discovery_run(db_session, service_id=service_id, principal=actor, now=NOW)


async def test_a_service_with_no_active_scoring_version_raises(db_session: AsyncSession) -> None:
    service_id = await _make_service(db_session, active_version=False)
    actor = await _make_actor(db_session)

    with pytest.raises(NoActiveScoringVersion):
        await request_discovery_run(db_session, service_id=service_id, principal=actor, now=NOW)


# --- accept_candidate (API-31, S-DSC-02) ----------------------------------------------------


async def test_accept_writes_the_account_links_the_candidate_and_queues_a_refresh(
    db_session: AsyncSession,
) -> None:
    service_id = await _make_service(db_session)
    run_id = await _make_run(db_session, service_id=service_id)
    actor = await _make_actor(db_session)
    candidate = await _make_candidate(
        db_session, service_id=service_id, run_id=run_id, country_code="DE"
    )

    result = await accept_candidate(
        db_session,
        candidate_id=candidate.id,
        domain="lufthansa.com",
        keys_configured=frozenset(),
        principal=actor,
        now=NOW,
    )

    account = (
        await db_session.execute(select(Account).where(Account.id == result.row.id))
    ).scalar_one()
    assert account.origin.value == "DISCOVERED"
    assert account.attribute_origin.get("country_code") == "MANUAL"

    await db_session.refresh(candidate)
    assert candidate.status == DiscoveryCandidateStatus.ACCEPTED
    assert candidate.account_id == account.id

    refresh_run = (
        await db_session.execute(select(PipelineRun).where(PipelineRun.account_id == account.id))
    ).scalar_one()
    assert refresh_run.kind == PipelineRunKind.ACCOUNT_REFRESH
    assert refresh_run.trigger == PipelineRunTrigger.USER

    actions = (
        (
            await db_session.execute(
                select(AuditEvent.action).where(
                    AuditEvent.action.in_(
                        [AuditAction.ACCOUNT_CREATED, AuditAction.CANDIDATE_ACCEPTED]
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    assert set(actions) == {AuditAction.ACCOUNT_CREATED, AuditAction.CANDIDATE_ACCEPTED}


async def test_accept_without_a_domain_and_none_on_the_candidate_raises_domain_required(
    db_session: AsyncSession,
) -> None:
    service_id = await _make_service(db_session)
    run_id = await _make_run(db_session, service_id=service_id)
    actor = await _make_actor(db_session)
    candidate = await _make_candidate(db_session, service_id=service_id, run_id=run_id, domain=None)

    with pytest.raises(CandidateDomainRequired):
        await accept_candidate(
            db_session,
            candidate_id=candidate.id,
            domain=None,
            keys_configured=frozenset(),
            principal=actor,
            now=NOW,
        )


async def test_accepting_an_already_decided_candidate_raises_candidate_not_pending(
    db_session: AsyncSession,
) -> None:
    service_id = await _make_service(db_session)
    run_id = await _make_run(db_session, service_id=service_id)
    actor = await _make_actor(db_session)
    candidate = await _make_candidate(
        db_session,
        service_id=service_id,
        run_id=run_id,
        status=DiscoveryCandidateStatus.REJECTED,
        decided_by=actor.id,
        decided_at=NOW,
    )

    with pytest.raises(CandidateNotPending):
        await accept_candidate(
            db_session,
            candidate_id=candidate.id,
            domain="lufthansa.com",
            keys_configured=frozenset(),
            principal=actor,
            now=NOW,
        )


async def test_accepting_an_unknown_candidate_raises_candidate_not_found(
    db_session: AsyncSession,
) -> None:
    actor = await _make_actor(db_session)
    with pytest.raises(CandidateNotFound):
        await accept_candidate(
            db_session,
            candidate_id=uuid.uuid4(),
            domain="lufthansa.com",
            keys_configured=frozenset(),
            principal=actor,
            now=NOW,
        )


# --- reject_candidate (API-32) --------------------------------------------------------------


async def test_reject_records_the_reason_and_decision(db_session: AsyncSession) -> None:
    service_id = await _make_service(db_session)
    run_id = await _make_run(db_session, service_id=service_id)
    actor = await _make_actor(db_session)
    candidate = await _make_candidate(db_session, service_id=service_id, run_id=run_id)

    result = await reject_candidate(
        db_session, candidate_id=candidate.id, reason="Too small.", principal=actor, now=NOW
    )

    assert result.status == DiscoveryCandidateStatus.REJECTED
    assert result.reject_reason == "Too small."
    await db_session.refresh(candidate)
    assert candidate.decided_by == actor.id
    assert candidate.decided_at == NOW
    audit = (
        await db_session.execute(
            select(AuditEvent).where(AuditEvent.action == AuditAction.CANDIDATE_REJECTED)
        )
    ).scalar_one()
    assert audit.entity_id == candidate.id
