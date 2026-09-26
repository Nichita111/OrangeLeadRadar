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

STEP_HANDLERS: Mapping[JobStep, StepHandler] = {}
