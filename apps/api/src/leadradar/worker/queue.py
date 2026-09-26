"""Job queue loop for the worker.

Claims one `READY` job per loop iteration with `SELECT … FOR UPDATE SKIP LOCKED`,
runs the registered step, marks `DONE` on success or retries/fails on error.
Reclaims `RUNNING` jobs past `JOB_LOCK_TIMEOUT_S`.

Only the `SCORE` step is registered; other steps are registered by their own tasks (P-06).

See [Job queue](/architecture/services/worker.md#job-queue) and
[ADR-04](/architecture/adrs/adr-04-postgres-job-queue-and-a-worker.md).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from leadradar.core.enums import JobStatus, JobStep, PipelineRunStage, PipelineRunStatus
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps.score import run_score_step

logger = logging.getLogger(__name__)

# Registry of step handlers; extended by other tasks (P-06).
_STEP_HANDLERS: dict[str, object] = {
    JobStep.SCORE: run_score_step,
}


async def _claim_job(session: AsyncSession, worker_id: str, now: datetime) -> Job | None:
    """Claim one READY job with FOR UPDATE SKIP LOCKED, ordered by priority then not_before."""
    stmt = (
        select(Job)
        .where(
            Job.status == JobStatus.READY,
            Job.not_before <= now,
        )
        .order_by(Job.priority, Job.not_before)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    job: Job | None = result.scalar_one_or_none()
    if job is None:
        return None

    # Mark as RUNNING
    await session.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(
            status=JobStatus.RUNNING,
            locked_by=worker_id,
            locked_at=now,
            attempts=job.attempts + 1,
        )
    )

    # Set run started_at on first claim
    await session.execute(
        update(PipelineRun)
        .where(
            PipelineRun.id == job.run_id,
            PipelineRun.started_at.is_(None),
        )
        .values(
            status=PipelineRunStatus.RUNNING,
            started_at=now,
            stage=PipelineRunStage.SCORE,
        )
    )
    await session.commit()

    # Reload the job after commit to get the updated state
    await session.refresh(job)
    return job


async def _reclaim_stale_jobs(
    session: AsyncSession, worker_id: str, now: datetime, lock_timeout_s: int
) -> None:
    """Return RUNNING jobs past JOB_LOCK_TIMEOUT_S to READY so they are re-picked."""
    cutoff = now - timedelta(seconds=lock_timeout_s)
    await session.execute(
        update(Job)
        .where(
            Job.status == JobStatus.RUNNING,
            Job.locked_at <= cutoff,
        )
        .values(
            status=JobStatus.READY,
            locked_by=None,
            locked_at=None,
        )
    )
    await session.commit()


async def _mark_done(session: AsyncSession, job_id: uuid.UUID) -> None:
    await session.execute(
        update(Job).where(Job.id == job_id).values(status=JobStatus.DONE)
    )
    await session.commit()


async def _mark_failed_or_retry(
    session: AsyncSession,
    job_id: uuid.UUID,
    error: str,
    attempts: int,
    max_attempts: int,
    backoff_s: int,
    now: datetime,
) -> None:
    if attempts >= max_attempts:
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status=JobStatus.FAILED, last_error=error)
        )
    else:
        # Exponential backoff: backoff_s × 2^(attempts−1)
        delay = backoff_s * (2 ** (attempts - 1))
        not_before = now + timedelta(seconds=delay)
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.READY,
                locked_by=None,
                locked_at=None,
                not_before=not_before,
                last_error=error,
            )
        )
    await session.commit()


async def _run_one(
    engine: AsyncEngine,
    settings: WorkerSettings,
    worker_id: str,
) -> bool:
    """Try to claim and execute one job. Returns True if a job was processed."""
    now = datetime.now(tz=UTC)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # Reclaim stale jobs
        await _reclaim_stale_jobs(session, worker_id, now, settings.job_lock_timeout_s)

        # Claim a job
        job = await _claim_job(session, worker_id, now)
        if job is None:
            return False

    job_id = job.id
    run_id = job.run_id
    attempts = job.attempts

    # Load the run
    async with factory() as session:
        run = await session.get(PipelineRun, run_id)
        if run is None:
            logger.error("Job %s references unknown run %s; marking FAILED", job_id, run_id)
            await _mark_failed_or_retry(
                session, job_id, "run not found", attempts,
                settings.job_max_attempts, settings.job_retry_backoff_s, now,
            )
            return True

        handler = _STEP_HANDLERS.get(str(job.step))
        if handler is None:
            logger.error("No handler for step %s; marking FAILED", job.step)
            await _mark_failed_or_retry(
                session, job_id, f"no handler for step {job.step}",
                attempts, settings.job_max_attempts, settings.job_retry_backoff_s, now,
            )
            return True

        try:
            import inspect
            if inspect.iscoroutinefunction(handler):
                import typing
                coro_fn: typing.Any = handler
                await coro_fn(
                    session,
                    job=job,
                    run=run,
                    worker_instance_id=worker_id,
                    alert_max_age_days=settings.alert_max_age_days,
                )
            await session.commit()
            await _mark_done(session, job_id)
        except Exception as exc:
            logger.exception("Step %s job %s failed (attempt %d)", job.step, job_id, attempts)
            await session.rollback()
            async with factory() as err_session:
                await _mark_failed_or_retry(
                    err_session, job_id, str(exc), attempts,
                    settings.job_max_attempts, settings.job_retry_backoff_s, now,
                )

    return True


async def run_job_loop(engine: AsyncEngine, settings: WorkerSettings, worker_id: str) -> None:
    """One job loop: poll for jobs until stopped by cancellation.

    Sleeps briefly when no job is available to avoid busy-polling.
    """
    while True:
        try:
            processed = await _run_one(engine, settings, worker_id)
            if not processed:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Unexpected error in job loop %s", worker_id)
            await asyncio.sleep(5)
