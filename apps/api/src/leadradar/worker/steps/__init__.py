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

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.ai.gateway import AiGateway
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
    """What a handler is given: its job, the open transaction's session, the time, the worker's
    configuration and the one [AI gateway](/architecture/services/worker.md#ai-gateway) instance
    of this process. Handlers that make no AI call (`SCORE`) ignore `gateway`."""

    job: ClaimedJob
    session: AsyncSession
    now: datetime
    settings: WorkerSettings
    gateway: AiGateway | None = None
    #: The client of the [Embedder](/architecture/interfaces.md#embedder), for `PROCESS` and for
    #: the question vectors of `SIGNAL`'s passage selection.
    embedder: httpx.AsyncClient | None = None
    #: Opens a session of its own, for a step whose work must not share the step's fate: the
    #: `FETCH` step reads its inputs before it uses the network, and commits its usage and
    #: errors whether or not the step later fails.
    sessions: Callable[[], AsyncSession] | None = None


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
    if context.gateway is None:
        raise RuntimeError("The SIGNAL step requires the AI gateway")
    if context.embedder is None:
        raise RuntimeError("The SIGNAL step requires the embedder client")
    await run_signal_job(
        context.session,
        job=job,
        run=run,
        settings=context.settings,
        gateway=context.gateway,
        embedder=context.embedder,
    )


async def _run_score(context: StepContext) -> None:
    """Adapts `run_score_step`, which takes the job and run rows, to the handler shape."""
    from leadradar.worker.steps.score import run_score_step

    _, run = await _load_job_and_run(context)
    await run_score_step(
        context.session,
        run=run,
        alert_max_age_days=context.settings.alert_max_age_days,
        now=context.now,
    )


async def _run_fetch(context: StepContext) -> None:
    from leadradar.worker.steps.fetch import run_fetch_step

    await run_fetch_step(context)


async def _run_process(context: StepContext) -> None:
    from leadradar.worker.steps.process import run_process_step

    await run_process_step(context)


async def _run_evaluate(context: StepContext) -> None:
    """Adapts `run_evaluate_job`, which takes the job and run rows and the AI gateway, to the
    handler shape."""
    from leadradar.worker.steps.evaluate import run_evaluate_job

    job, run = await _load_job_and_run(context)
    if context.gateway is None:
        raise RuntimeError("The EVALUATE step requires the AI gateway")
    await run_evaluate_job(
        context.session, job=job, run=run, settings=context.settings, gateway=context.gateway
    )


STEP_HANDLERS: Mapping[JobStep, StepHandler] = {
    JobStep.FETCH: _run_fetch,
    JobStep.PROCESS: _run_process,
    JobStep.SIGNAL: _run_signal,
    JobStep.SCORE: _run_score,
    JobStep.EVALUATE: _run_evaluate,
}
