"""The job loop of the [Job queue](/architecture/services/worker.md#job-queue): reclaim abandoned
jobs, claim the next one, run its step's handler in one transaction with the job's completion,
and on failure retry it with backoff or fail it. A worker process runs `WORKER_CONCURRENCY` of
these loops."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import JobStep
from leadradar.core.job_queue import next_attempt_at
from leadradar.logs import run_id_var
from leadradar.worker.queue import (
    LostJobLock,
    claim_next_job,
    complete_job,
    reclaim_abandoned_jobs,
    record_job_failure,
)
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import (
    ClaimedJob,
    StepContext,
    StepErrorCode,
    StepFailed,
    StepHandler,
)

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AsyncSession]
Clock = Callable[[], datetime]


async def _record_failure(
    session_factory: SessionFactory,
    job: ClaimedJob,
    *,
    worker_id: str,
    code: StepErrorCode,
    message: str,
    retry_at: datetime | None,
    settings: WorkerSettings,
    clock: Clock,
) -> None:
    try:
        async with session_factory() as session, session.begin():
            await record_job_failure(
                session,
                job,
                worker_id=worker_id,
                code=code,
                message=message,
                retry_at=retry_at,
                now=clock(),
                refresh_interval_hours=settings.refresh_interval_hours,
            )
    except LostJobLock:
        logger.warning("Job %s was reclaimed while it ran; its failure is not recorded", job.id)


async def _run_claimed_job(
    session_factory: SessionFactory,
    job: ClaimedJob,
    *,
    handlers: Mapping[JobStep, StepHandler],
    settings: WorkerSettings,
    clock: Clock,
    worker_id: str,
) -> None:
    handler = handlers.get(job.step)
    if handler is None:
        # No code for this step: nothing ran, so nothing may be marked done, and a retry
        # would fail the same way.
        await _record_failure(
            session_factory,
            job,
            worker_id=worker_id,
            code="INTERNAL",
            message=f"The worker has no handler for step {job.step.value}.",
            retry_at=None,
            settings=settings,
            clock=clock,
        )
        return

    try:
        async with session_factory() as session, session.begin():
            await handler(StepContext(job=job, session=session, now=clock(), settings=settings))
            await complete_job(
                session,
                job,
                worker_id=worker_id,
                now=clock(),
                refresh_interval_hours=settings.refresh_interval_hours,
            )
    except LostJobLock:
        logger.warning("Job %s was reclaimed while it ran; its results were rolled back", job.id)
    except Exception as error:
        # Acted on, not swallowed: the attempt is recorded, and retried or failed.
        logger.exception("Step %s of job %s failed", job.step.value, job.id)
        await _record_failure(
            session_factory,
            job,
            worker_id=worker_id,
            code=error.code if isinstance(error, StepFailed) else "INTERNAL",
            message=str(error) or type(error).__name__,
            retry_at=next_attempt_at(
                attempts=job.attempts,
                max_attempts=settings.job_max_attempts,
                backoff_s=settings.job_retry_backoff_s,
                now=clock(),
            ),
            settings=settings,
            clock=clock,
        )


async def process_next_job(
    session_factory: SessionFactory,
    *,
    handlers: Mapping[JobStep, StepHandler],
    settings: WorkerSettings,
    clock: Clock,
    worker_id: str,
) -> bool:
    """Runs one job to its outcome; `False` when no job was due."""
    async with session_factory() as session, session.begin():
        now = clock()
        await reclaim_abandoned_jobs(session, now=now, lock_timeout_s=settings.job_lock_timeout_s)
        job = await claim_next_job(session, worker_id=worker_id, now=now)
    if job is None:
        return False

    token = run_id_var.set(str(job.run_id))
    try:
        await _run_claimed_job(
            session_factory,
            job,
            handlers=handlers,
            settings=settings,
            clock=clock,
            worker_id=worker_id,
        )
    finally:
        run_id_var.reset(token)
    return True


async def run_job_loop(
    session_factory: SessionFactory,
    *,
    handlers: Mapping[JobStep, StepHandler],
    settings: WorkerSettings,
    clock: Clock,
    worker_id: str,
    stop: asyncio.Event,
) -> None:
    """Processes jobs until `stop` is set, finishing the job in hand first; waits
    `JOB_POLL_INTERVAL_S` whenever no job is due."""
    while not stop.is_set():
        try:
            processed = await process_next_job(
                session_factory,
                handlers=handlers,
                settings=settings,
                clock=clock,
                worker_id=worker_id,
            )
        except Exception:
            # The database is unreachable or refused the claim: logged, and tried again after
            # the poll interval rather than ending the loop.
            logger.exception("Job loop %s could not claim or record a job", worker_id)
            processed = False
        if not processed:
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=settings.job_poll_interval_s)
