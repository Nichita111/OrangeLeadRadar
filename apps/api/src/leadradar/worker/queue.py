"""Store access of the [Job queue](/architecture/services/worker.md#job-queue) and the
[Run lifecycle](/architecture/services/worker.md#run-lifecycle): reclaiming abandoned jobs,
claiming, completing and failing a job, and settling its run once its jobs are final. The
decisions are the pure rules of `core.run_lifecycle`, `core.job_queue` and
`core.refresh_scheduling`; none of these functions commits.

Every function that touches both locks the job row before the run row, as `runs.cancel_run`
does, so two transactions never wait on each other in a cycle."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.core.enums import AuditAction, JobStatus, PipelineRunKind, PipelineRunStatus
from leadradar.core.job_queue import job_priority
from leadradar.core.refresh_scheduling import refresh_times_after
from leadradar.core.run_lifecycle import (
    FINAL_STEP,
    owed_final_job,
    run_outcome,
    stage_after_claim,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.runs.enqueue import add_job
from leadradar.worker.steps import ClaimedJob, StepErrorCode

_ACTIVE_RUN_STATUSES = (PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING)
_OPEN_JOB_STATUSES = (JobStatus.READY, JobStatus.RUNNING)


class LostJobLock(Exception):
    """The job is no longer `RUNNING` under this worker: it was reclaimed after
    `JOB_LOCK_TIMEOUT_S`, and the worker that claimed it since owns its outcome."""


async def reclaim_abandoned_jobs(
    session: AsyncSession, *, now: datetime, lock_timeout_s: int
) -> int:
    """Returns every `RUNNING` job locked longer than `JOB_LOCK_TIMEOUT_S` ago to `READY`, and
    says how many. Safe because every step is idempotent ([N-05](/requirements/system.md))."""
    reclaimed = await session.execute(
        update(Job)
        .where(
            Job.status == JobStatus.RUNNING,
            Job.locked_at < now - timedelta(seconds=lock_timeout_s),
        )
        .values(status=JobStatus.READY, locked_by=None, locked_at=None)
        .returning(Job.id)
        .execution_options(synchronize_session=False)
    )
    return len(reclaimed.all())


async def _lock_run(session: AsyncSession, run_id: uuid.UUID) -> PipelineRun:
    run = await session.get(PipelineRun, run_id, with_for_update=True, populate_existing=True)
    if run is None:
        raise LookupError(f"Job of run {run_id}, which does not exist.")
    return run


async def claim_next_job(
    session: AsyncSession, *, worker_id: str, now: datetime
) -> ClaimedJob | None:
    """Claims the next `READY` job due by `now` — lowest `priority`, then earliest
    `not_before` — with `FOR UPDATE SKIP LOCKED`, so concurrent loops never claim the same one.
    Sets its run `RUNNING` with `started_at` on its first claim and moves its `stage`. A job of a
    cancelled run is set `CANCELLED` instead and the next one is tried. `None` when no job is
    due."""
    while True:
        candidate = (
            select(Job.id)
            .where(Job.status == JobStatus.READY, Job.not_before <= now)
            .order_by(Job.priority, Job.not_before)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        claimed = (
            await session.execute(
                update(Job)
                .where(Job.id == candidate)
                .values(
                    status=JobStatus.RUNNING,
                    attempts=Job.attempts + 1,
                    locked_by=worker_id,
                    locked_at=now,
                )
                .returning(Job.id, Job.run_id, Job.step, Job.payload, Job.attempts)
                .execution_options(synchronize_session=False)
            )
        ).first()
        if claimed is None:
            return None
        job_id, run_id, step, payload, attempts = claimed

        run = await _lock_run(session, run_id)
        if run.status not in _ACTIVE_RUN_STATUSES:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status=JobStatus.CANCELLED, locked_by=None, locked_at=None)
                .execution_options(synchronize_session=False)
            )
            continue

        if run.status is PipelineRunStatus.QUEUED:
            run.status = PipelineRunStatus.RUNNING
            run.started_at = now
        run.stage = stage_after_claim(run.stage, step)
        await session.flush()
        return ClaimedJob(
            id=job_id,
            step=step,
            payload=payload,
            attempts=attempts,
            run_id=run.id,
            run_kind=run.kind,
            run_trigger=run.trigger,
            account_id=run.account_id,
            service_id=run.service_id,
            question_id=run.question_id,
        )


async def _finish_job(
    session: AsyncSession, job: ClaimedJob, *, worker_id: str, values: dict[str, object]
) -> None:
    """Updates the job this worker holds; raises `LostJobLock` when it no longer holds it."""
    updated = await session.execute(
        update(Job)
        .where(
            Job.id == job.id,
            Job.status == JobStatus.RUNNING,
            Job.locked_by == worker_id,
        )
        .values(locked_by=None, locked_at=None, **values)
        .returning(Job.id)
        .execution_options(synchronize_session=False)
    )
    if updated.first() is None:
        raise LostJobLock(f"Job {job.id} is no longer held by {worker_id}.")


async def complete_job(
    session: AsyncSession,
    job: ClaimedJob,
    *,
    worker_id: str,
    now: datetime,
    refresh_interval_hours: int,
) -> None:
    """Sets the job `DONE`, in the transaction of its step's results, and settles its run."""
    await _finish_job(session, job, worker_id=worker_id, values={"status": JobStatus.DONE})
    run = await _lock_run(session, job.run_id)
    await _settle_run(
        session,
        run,
        job,
        job_failed=False,
        now=now,
        refresh_interval_hours=refresh_interval_hours,
    )


async def record_job_failure(
    session: AsyncSession,
    job: ClaimedJob,
    *,
    worker_id: str,
    code: StepErrorCode,
    message: str,
    retry_at: datetime | None,
    now: datetime,
    refresh_interval_hours: int,
) -> None:
    """After a failed attempt: the job is `READY` again from `retry_at`, or, with `retry_at`
    `None`, `FAILED`, its run records the error, and the run is settled."""
    if retry_at is not None:
        await _finish_job(
            session,
            job,
            worker_id=worker_id,
            values={"status": JobStatus.READY, "not_before": retry_at, "last_error": message},
        )
        return

    await _finish_job(
        session,
        job,
        worker_id=worker_id,
        values={"status": JobStatus.FAILED, "last_error": message},
    )
    run = await _lock_run(session, job.run_id)
    error: dict[str, object] = {
        "stage": stage_after_claim(run.stage, job.step).value,
        "code": code,
        "message": message,
    }
    plugin_code = job.payload.get("plugin_code")
    if plugin_code is not None:
        error["plugin_code"] = plugin_code
    run.errors = [*run.errors, error]
    await session.flush()
    await _settle_run(
        session,
        run,
        job,
        job_failed=True,
        now=now,
        refresh_interval_hours=refresh_interval_hours,
    )


async def _settle_run(
    session: AsyncSession,
    run: PipelineRun,
    job: ClaimedJob,
    *,
    job_failed: bool,
    now: datetime,
    refresh_interval_hours: int,
) -> None:
    """With the run locked and `job` just final: when every job of the run is final, enqueues
    the `SCORE` job the run is owed, or finishes the run with its `RUN_FINISHED` audit row and,
    for a refresh, the account's refresh times. A cancelled run is left as it is."""
    if run.status not in _ACTIVE_RUN_STATUSES:
        return
    jobs = (await session.execute(select(Job.step, Job.status).where(Job.run_id == run.id))).all()
    if any(status in _OPEN_JOB_STATUSES for _, status in jobs):
        return

    owed = owed_final_job(run.kind, {step for step, _ in jobs})
    if owed is not None:
        add_job(
            session,
            run_id=run.id,
            step=owed,
            payload={},
            priority=job_priority(run.kind, run.trigger),
            now=now,
        )
        await session.flush()
        return

    pending_budget = run.progress.get("pending_budget", 0)
    if not isinstance(pending_budget, int):
        raise TypeError(f"Run {run.id} progress.pending_budget is not a count: {pending_budget!r}")
    run.status = run_outcome(
        final_stage_failed=job_failed and job.step is FINAL_STEP[run.kind],
        has_errors=bool(run.errors),
        pending_budget=pending_budget,
    )
    run.stage = None
    run.finished_at = now
    await append_audit_event(
        session,
        action=AuditAction.RUN_FINISHED,
        occurred_at=now,
        actor_id=None,
        entity_type="pipeline_run",
        entity_id=run.id,
        payload={"status": run.status.value, "progress": run.progress},
        run_id=run.id,
    )

    if run.kind is PipelineRunKind.ACCOUNT_REFRESH and run.account_id is not None:
        times = refresh_times_after(run.status, now, refresh_interval_hours=refresh_interval_hours)
        account = await session.get(Account, run.account_id, with_for_update=True)
        if times is not None and account is not None:
            account.next_refresh_at = times.next_refresh_at
            if times.last_refreshed_at is not None:
                account.last_refreshed_at = times.last_refreshed_at
    await session.flush()
