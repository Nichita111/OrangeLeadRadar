"""The step handlers the job loop runs, keyed by [`job`](/architecture/sql-store.md#job) `step`.

A handler receives its job and the session of the one transaction it shares with the job's
completion: it writes its results, and enqueues the next stage's jobs when it finishes a stage,
through that session, and the loop marks the job `DONE` in the same commit
([Job queue](/architecture/services/worker.md#job-queue) Fan-out). A handler that cannot do its
work raises — `StepFailed` to name the error code its run records, anything else records
`INTERNAL` — and the loop retries it with backoff.

A step with no handler here is never run: its jobs fail at once. Each task that builds a step
registers it with one line in `STEP_HANDLERS`."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import JobStep, PipelineRunKind, PipelineRunTrigger
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.worker.settings import WorkerSettings

# An error code of [Conventions](/architecture/interfaces.md#conventions), or `FIXTURE_MISSING`,
# as [`pipeline_run`](/architecture/sql-store.md#pipeline_run) `errors` allows.
StepErrorCode = Literal[
    "UPSTREAM_UNAVAILABLE", "BUDGET_EXHAUSTED", "NOT_CONFIGURED", "FIXTURE_MISSING", "INTERNAL"
]


@dataclass(frozen=True)
class ClaimedJob:
    """A job the loop has claimed, with the scope of its run."""

    id: uuid.UUID
    step: JobStep
    payload: dict[str, object]
    attempts: int
    run_id: uuid.UUID
    run_kind: PipelineRunKind
    run_trigger: PipelineRunTrigger
    account_id: uuid.UUID | None
    service_id: uuid.UUID | None
    question_id: uuid.UUID | None


@dataclass(frozen=True)
class StepContext:
    """What a handler is given: its job, the open transaction's session, the time and the
    worker's configuration."""

    job: ClaimedJob
    session: AsyncSession
    now: datetime
    settings: WorkerSettings


class StepFailed(Exception):
    """Raised by a handler that failed with a known error code."""

    def __init__(self, code: StepErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: StepErrorCode = code


StepHandler = Callable[[StepContext], Awaitable[None]]


async def _load_job_and_run(context: StepContext) -> tuple[Job, PipelineRun]:
    job = await context.session.get(Job, context.job.id)
    run = await context.session.get(PipelineRun, context.job.run_id)
    if job is None or run is None:
        raise LookupError(f"Job {context.job.id} or its run {context.job.run_id} does not exist.")
    return job, run


async def _run_signal(context: StepContext) -> None:
    """Adapts `run_signal_job`, which takes the job and run rows, to the handler shape."""
    from leadradar.worker.steps.signal import run_signal_job

    job, run = await _load_job_and_run(context)
    await run_signal_job(
        context.session,
        job=job,
        run=run,
        worker_instance_id=str(context.job.id),
        alert_max_age_days=context.settings.alert_max_age_days,
        settings=context.settings,
    )


async def _run_score(context: StepContext) -> None:
    """Adapts `run_score_step`, which takes the job and run rows, to the handler shape."""
    from leadradar.worker.steps.score import run_score_step

    job, run = await _load_job_and_run(context)
    await run_score_step(
        context.session,
        job=job,
        run=run,
        worker_instance_id=str(context.job.id),
        alert_max_age_days=context.settings.alert_max_age_days,
    )


STEP_HANDLERS: Mapping[JobStep, StepHandler] = {
    JobStep.SIGNAL: _run_signal,
    JobStep.SCORE: _run_score,
}
