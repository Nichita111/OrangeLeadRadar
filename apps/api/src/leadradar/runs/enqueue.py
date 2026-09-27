"""Enqueues a `RESCORE` run and its one `SCORE` job
([api Design](/architecture/services/api.md#design) Enqueueing,
[Run lifecycle](/architecture/services/worker.md#run-lifecycle) with D3, G7 (a) of
`.work/lead-signal-feedback/task.md`). Reused by every capability that needs to rescore one
account and service: this task's feedback capability passes trigger `FEEDBACK`; later tasks pass
`OVERRIDE` and `ACCOUNT_CHANGE`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
)
from leadradar.core.job_queue import job_priority
from leadradar.db.models.ingestion import Job, PipelineRun


async def enqueue_account_rescore(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    trigger: PipelineRunTrigger,
    requested_by: uuid.UUID,
    now: datetime,
) -> uuid.UUID:
    """Inserts the `pipeline_run` and its `job` in the caller's transaction; does not commit."""
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

    session.add(
        Job(
            run_id=run.id,
            step=JobStep.SCORE,
            payload={},
            status=JobStatus.READY,
            priority=job_priority(PipelineRunKind.RESCORE, trigger),
            attempts=0,
            not_before=now,
            locked_by=None,
            locked_at=None,
            last_error=None,
        )
    )
    await session.flush()
    return run.id
