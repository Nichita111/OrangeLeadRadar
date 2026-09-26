"""Queue a `RECLASSIFY` run after a question is created, reactivated or revised
([Reclassification](/architecture/rules.md#reclassification), `S-SIG-07`).

One `SIGNAL` job per active account, at the priority the
[Job queue](/architecture/services/worker.md#job-queue) gives `RECLASSIFY`; the last one to
finish enqueues the run's `SCORE` job. With no active account, the `SCORE` job is enqueued
directly. The caller owns the transaction.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import write_run_requested
from leadradar.core.enums import (
    AccountStatus,
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import SignalQuestion
from leadradar.db.models.ingestion import Job, PipelineRun

RECLASSIFY_PRIORITY = 3


async def queue_reclassify(
    session: AsyncSession,
    *,
    question_id: uuid.UUID,
    actor_id: uuid.UUID,
    request_id: str | None,
) -> uuid.UUID:
    """Create the `RECLASSIFY` run for `question_id` and its jobs; return the run id."""
    question = await session.get(SignalQuestion, question_id)
    if question is None:
        raise ValueError(f"signal question {question_id} not found")

    now = datetime.now(tz=UTC)
    run_id = uuid.uuid4()
    session.add(
        PipelineRun(
            id=run_id,
            kind=PipelineRunKind.RECLASSIFY,
            trigger=PipelineRunTrigger.QUESTION_CHANGE,
            account_id=None,
            service_id=question.service_id,
            question_id=question_id,
            status=PipelineRunStatus.QUEUED,
            stage=None,
            progress={},
            errors=[],
            requested_by=actor_id,
        )
    )
    await session.flush()

    account_ids = (
        await session.execute(select(Account.id).where(Account.status == AccountStatus.ACTIVE))
    ).scalars()
    jobs = [
        _job(run_id, JobStep.SIGNAL, now, account_id=str(a), question_id=str(question_id))
        for a in account_ids
    ]
    session.add_all(jobs or [_job(run_id, JobStep.SCORE, now)])

    await write_run_requested(
        session,
        actor_id=actor_id,
        run_id=run_id,
        kind=PipelineRunKind.RECLASSIFY,
        trigger=PipelineRunTrigger.QUESTION_CHANGE,
        request_id=request_id,
    )
    await session.flush()
    return run_id


def _job(run_id: uuid.UUID, step: JobStep, now: datetime, **payload: str) -> Job:
    return Job(
        run_id=run_id,
        step=step,
        payload=payload,
        status=JobStatus.READY,
        priority=RECLASSIFY_PRIORITY,
        attempts=0,
        not_before=now,
    )
