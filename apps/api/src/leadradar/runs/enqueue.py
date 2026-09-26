"""Enqueues runs and their jobs ([api Design](/architecture/services/api.md#design) Enqueueing,
[Run lifecycle](/architecture/services/worker.md#run-lifecycle)): the one place a `pipeline_run`
and its jobs are inserted. `enqueue_account_rescore` serves every capability that rescores one
account and service (feedback, overrides, account changes); `enqueue_account_refresh` serves
`API-33` and the scheduler; `add_job` also serves the worker's job loop when it enqueues a job a
run is owed. None of them commits: the caller's transaction owns the write."""

from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
    SourcePluginCode,
)
from leadradar.core.job_queue import job_priority
from leadradar.core.run_lifecycle import refresh_first_jobs
from leadradar.db.models.ingestion import Job, PipelineRun

_ACTIVE_STATUSES = (PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING)


def add_job(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    step: JobStep,
    payload: dict[str, object],
    priority: int,
    now: datetime,
) -> None:
    """Adds one `READY` job of the run, startable from `now`."""
    session.add(
        Job(
            run_id=run_id,
            step=step,
            payload=payload,
            status=JobStatus.READY,
            priority=priority,
            attempts=0,
            not_before=now,
            locked_by=None,
            locked_at=None,
            last_error=None,
        )
    )


async def enqueue_account_rescore(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    trigger: PipelineRunTrigger,
    requested_by: uuid.UUID,
    now: datetime,
) -> uuid.UUID:
    """Inserts a `RESCORE` `pipeline_run` and its one `SCORE` job."""
    run = PipelineRun(
        kind=PipelineRunKind.RESCORE,
        trigger=trigger,
        account_id=account_id,
        service_id=service_id,
        question_id=None,
        status=PipelineRunStatus.QUEUED,
        stage=None,
        progress={},
        errors=[],
        requested_by=requested_by,
        started_at=None,
        finished_at=None,
    )
    session.add(run)
    await session.flush()

    add_job(
        session,
        run_id=run.id,
        step=JobStep.SCORE,
        payload={},
        priority=job_priority(PipelineRunKind.RESCORE, trigger),
        now=now,
    )
    await session.flush()
    return run.id


async def enqueue_account_refresh(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    trigger: PipelineRunTrigger,
    requested_by: uuid.UUID | None,
    available_plugins: Collection[SourcePluginCode],
    now: datetime,
) -> tuple[uuid.UUID, bool]:
    """Inserts a `QUEUED` `ACCOUNT_REFRESH` run with its first-stage jobs and returns
    `(run_id, True)`; when the account already has a queued or running refresh, inserts nothing
    and returns `(that run's id, False)`. The partial unique index of one active refresh per
    account decides, so two concurrent requests converge on one run
    ([Constraints and indexes](/architecture/sql-store.md#constraints-and-indexes))."""
    inserted = await session.execute(
        insert(PipelineRun)
        .values(
            kind=PipelineRunKind.ACCOUNT_REFRESH,
            trigger=trigger,
            account_id=account_id,
            service_id=None,
            question_id=None,
            status=PipelineRunStatus.QUEUED,
            stage=None,
            progress={},
            errors=[],
            requested_by=requested_by,
            started_at=None,
            finished_at=None,
        )
        .on_conflict_do_nothing(
            index_elements=["account_id"],
            index_where=text("kind = 'ACCOUNT_REFRESH' AND status IN ('QUEUED', 'RUNNING')"),
        )
        .returning(PipelineRun.id)
    )
    run_id = inserted.scalar_one_or_none()
    if run_id is None:
        existing = await session.execute(
            select(PipelineRun.id).where(
                PipelineRun.account_id == account_id,
                PipelineRun.kind == PipelineRunKind.ACCOUNT_REFRESH,
                PipelineRun.status.in_(_ACTIVE_STATUSES),
            )
        )
        return existing.scalar_one(), False

    priority = job_priority(PipelineRunKind.ACCOUNT_REFRESH, trigger)
    for step, payload in refresh_first_jobs(available_plugins):
        add_job(session, run_id=run_id, step=step, payload=payload, priority=priority, now=now)
    await session.flush()
    return run_id, True


async def enqueue_service_discovery(
    session: AsyncSession, *, service_id: uuid.UUID, requested_by: uuid.UUID, now: datetime
) -> tuple[uuid.UUID, bool]:
    """Inserts a `QUEUED` `DISCOVERY` run with its one `DISCOVER` job and returns
    `(run_id, True)`; when the service already has a queued or running discovery, inserts nothing
    and returns `(that run's id, False)` (`API-29`, `S-DSC-01`: "one queued or running discovery
    per service; a second request returns it"). The partial unique index of one active discovery
    per service decides, so two concurrent requests converge on one run."""
    inserted = await session.execute(
        insert(PipelineRun)
        .values(
            kind=PipelineRunKind.DISCOVERY,
            trigger=PipelineRunTrigger.USER,
            account_id=None,
            service_id=service_id,
            question_id=None,
            status=PipelineRunStatus.QUEUED,
            stage=None,
            progress={},
            errors=[],
            requested_by=requested_by,
            started_at=None,
            finished_at=None,
        )
        .on_conflict_do_nothing(
            index_elements=["service_id"],
            index_where=text("kind = 'DISCOVERY' AND status IN ('QUEUED', 'RUNNING')"),
        )
        .returning(PipelineRun.id)
    )
    run_id = inserted.scalar_one_or_none()
    if run_id is None:
        existing = await session.execute(
            select(PipelineRun.id).where(
                PipelineRun.service_id == service_id,
                PipelineRun.kind == PipelineRunKind.DISCOVERY,
                PipelineRun.status.in_(_ACTIVE_STATUSES),
            )
        )
        return existing.scalar_one(), False

    add_job(
        session,
        run_id=run_id,
        step=JobStep.DISCOVER,
        payload={},
        priority=job_priority(PipelineRunKind.DISCOVERY, PipelineRunTrigger.USER),
        now=now,
    )
    await session.flush()
    return run_id, True
