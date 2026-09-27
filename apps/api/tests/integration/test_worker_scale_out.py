"""Scale-out evidence for [N-11](/requirements/system.md) and the worker's
[Job queue](/architecture/services/worker.md#job-queue) claim log line (`AC-66`, decision G2):
two worker containers claim from one queue with `FOR UPDATE SKIP LOCKED`, so every job runs
exactly once and a second worker adds throughput rather than waiting on the first; each claim
writes one log line naming the job, its step and the claiming loop's `worker_id`.

The throughput and log-fan-out tests need genuine concurrent database connections, so they build
their own engines on `database_url` rather than the single shared transaction the other job-queue
tests roll back; they clean up the rows they committed, as
`test_concurrent_claims_never_take_the_same_job` does."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, delete, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from leadradar.core.enums import JobStatus, JobStep, PipelineRunKind, PipelineRunStatus
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.db.session import build_engine
from leadradar.logs import configure_json_logging
from leadradar.worker.loop import process_next_job, run_job_loop
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import StepContext
from tests.integration import factories as f

pytestmark = pytest.mark.integration

#: Older than any job another test leaves committed, so a drain never picks up a foreign job once
#: this test's own jobs run out (Risks, `design.md`).
OLD = datetime(2020, 1, 1, tzinfo=UTC)
SETTINGS = WorkerSettings(database_url=SecretStr("postgresql://unused"))


def _clock() -> datetime:
    return datetime.now(tz=UTC)


def _session_factory(engine: AsyncEngine) -> Callable[[], AsyncSession]:
    def make() -> AsyncSession:
        return AsyncSession(engine, expire_on_commit=False)

    return make


def _make_rescore_jobs(conn: Connection, count: int) -> tuple[list[uuid.UUID], set[uuid.UUID]]:
    run_ids: list[uuid.UUID] = []
    job_ids: set[uuid.UUID] = set()
    for _ in range(count):
        run_id = f.make_pipeline_run(conn, kind=PipelineRunKind.RESCORE)
        run_ids.append(run_id)
        job_ids.add(f.make_job(conn, run_id, priority=-1, not_before=OLD))
    return run_ids, job_ids


async def _cleanup(engine: AsyncEngine, run_ids: list[uuid.UUID]) -> None:
    """Deletes this test's jobs. A run that reached a final status wrote a `RUN_FINISHED`
    [audit row](/architecture/sql-store.md#audit_event) (`RULE-09`), and the application role may
    only insert and select `audit_event` (`AC-55`), never delete it, so its `pipeline_run` cannot
    be deleted either; it is left, as every run this test drives to completion is by design."""
    async with engine.begin() as conn:
        await conn.execute(delete(Job).where(Job.run_id.in_(run_ids)))


async def _stop_once_final(
    engine: AsyncEngine, job_ids: set[uuid.UUID], stop: asyncio.Event, poll_s: float
) -> None:
    """Sets `stop` once every one of `job_ids` is `DONE` or `FAILED`."""
    while True:
        async with engine.connect() as conn:
            statuses = (
                (await conn.execute(select(Job.status).where(Job.id.in_(job_ids)))).scalars().all()
            )
        if statuses and all(status in (JobStatus.DONE, JobStatus.FAILED) for status in statuses):
            stop.set()
            return
        await asyncio.sleep(poll_s)


async def test_two_workers_on_one_queue_run_every_job_exactly_once(database_url: str) -> None:
    engine_a = build_engine(database_url)
    engine_b = build_engine(database_url)
    handled: list[tuple[uuid.UUID, str]] = []

    async def handler(context: StepContext) -> None:
        assert context.sessions is not None
        async with context.sessions() as session:
            row = await session.get(Job, context.job.id)
            assert row is not None and row.locked_by is not None
            handled.append((context.job.id, row.locked_by))

    async with engine_a.begin() as setup:
        run_ids, job_ids = await setup.run_sync(lambda conn: _make_rescore_jobs(conn, 6))

    settings = SETTINGS.model_copy(update={"worker_concurrency": 2, "job_poll_interval_s": 0.02})
    stop = asyncio.Event()
    tasks = [
        run_job_loop(
            _session_factory(engine),
            handlers={JobStep.SCORE: handler},
            settings=settings,
            clock=_clock,
            worker_id=f"worker-{worker}:{loop_index}",
            stop=stop,
        )
        for worker, engine in enumerate((engine_a, engine_b))
        for loop_index in range(settings.worker_concurrency)
    ]
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, _stop_once_final(engine_a, job_ids, stop, 0.02)), timeout=15
        )
        async with AsyncSession(engine_a, expire_on_commit=False) as session:
            jobs = (await session.execute(select(Job).where(Job.id.in_(job_ids)))).scalars().all()
            runs = (
                (await session.execute(select(PipelineRun).where(PipelineRun.id.in_(run_ids))))
                .scalars()
                .all()
            )
    finally:
        await _cleanup(engine_a, run_ids)
        await engine_a.dispose()
        await engine_b.dispose()

    assert {job_id for job_id, _ in handled} == job_ids
    assert len(handled) == len(job_ids)
    assert {(job.status, job.attempts) for job in jobs} == {(JobStatus.DONE, 1)}
    assert {run.status for run in runs} == {PipelineRunStatus.SUCCEEDED}
    assert {worker_id.split(":")[0] for _, worker_id in handled} == {"worker-0", "worker-1"}


async def test_a_second_worker_runs_a_job_while_the_first_is_busy(database_url: str) -> None:
    engine_a = build_engine(database_url)
    engine_b = build_engine(database_url)
    barrier = asyncio.Barrier(2)

    async def handler(context: StepContext) -> None:
        # Both handlers must reach the barrier for either to pass it: this only happens if both
        # jobs are RUNNING, on two workers, at the same time.
        await asyncio.wait_for(barrier.wait(), timeout=5)

    async with engine_a.begin() as setup:
        run_ids, job_ids = await setup.run_sync(lambda conn: _make_rescore_jobs(conn, 2))

    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                process_next_job(
                    _session_factory(engine_a),
                    handlers={JobStep.SCORE: handler},
                    settings=SETTINGS,
                    clock=_clock,
                    worker_id="worker-a:0",
                ),
                process_next_job(
                    _session_factory(engine_b),
                    handlers={JobStep.SCORE: handler},
                    settings=SETTINGS,
                    clock=_clock,
                    worker_id="worker-b:0",
                ),
            ),
            timeout=10,
        )
        async with AsyncSession(engine_a, expire_on_commit=False) as session:
            jobs = (await session.execute(select(Job).where(Job.id.in_(job_ids)))).scalars().all()
    finally:
        await _cleanup(engine_a, run_ids)
        await engine_a.dispose()
        await engine_b.dispose()

    assert results == (True, True)
    assert {job.status for job in jobs} == {JobStatus.DONE}
    assert {job.locked_by for job in jobs} == {None}  # cleared once each job is DONE


@pytest.fixture
async def connection(async_connection: AsyncConnection) -> AsyncIterator[AsyncConnection]:
    """Cancels jobs other tests left `READY` or `RUNNING`, as `test_job_queue.py` does, so a
    single-loop drain here never claims one of them."""
    await async_connection.execute(
        update(Job)
        .where(Job.status.in_((JobStatus.READY, JobStatus.RUNNING)))
        .values(status=JobStatus.CANCELLED)
    )
    yield async_connection


def _single_session_factory(connection: AsyncConnection) -> Callable[[], AsyncSession]:
    def make() -> AsyncSession:
        return AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    return make


async def test_a_single_one_loop_worker_never_runs_two_jobs_at_once(
    connection: AsyncConnection,
) -> None:
    """The control for the test above: with only one loop ever calling the handler, the barrier
    of two never fills, so the same barrier handler times out on its first job, which is retried
    per [Retries](/architecture/services/worker.md#job-queue) rather than completing."""
    barrier = asyncio.Barrier(2)

    async def handler(context: StepContext) -> None:
        await asyncio.wait_for(barrier.wait(), timeout=0.05)

    def build(conn: Connection) -> list[uuid.UUID]:
        run_id = f.make_pipeline_run(conn, kind=PipelineRunKind.RESCORE)
        return [f.make_job(conn, run_id, not_before=OLD) for _ in range(2)]

    job_ids = await connection.run_sync(build)
    session_factory = _single_session_factory(connection)

    assert (
        await process_next_job(
            session_factory,
            handlers={JobStep.SCORE: handler},
            settings=SETTINGS,
            clock=_clock,
            worker_id="worker-1",
        )
        is True
    )
    assert (
        await process_next_job(
            session_factory,
            handlers={JobStep.SCORE: handler},
            settings=SETTINGS,
            clock=_clock,
            worker_id="worker-1",
        )
        is True
    )

    async with session_factory() as session:
        jobs = (await session.execute(select(Job).where(Job.id.in_(job_ids)))).scalars().all()
    assert {job.status for job in jobs} == {JobStatus.READY}
    assert all(job.last_error for job in jobs)


def _claim_lines(output: str) -> list[dict[str, object]]:
    lines = []
    for line in output.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if "job_id" in record:
            lines.append(record)
    return lines


async def test_claiming_a_job_logs_one_line_naming_the_job_its_step_and_the_worker(
    connection: AsyncConnection, capsys: pytest.CaptureFixture[str]
) -> None:
    def build(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        run_id = f.make_pipeline_run(conn, kind=PipelineRunKind.RESCORE)
        job_id = f.make_job(conn, run_id, not_before=OLD)
        return run_id, job_id

    run_id, job_id = await connection.run_sync(build)
    configure_json_logging("INFO")

    async def succeed(context: StepContext) -> None:
        return None

    processed = await process_next_job(
        _single_session_factory(connection),
        handlers={JobStep.SCORE: succeed},
        settings=SETTINGS,
        clock=_clock,
        worker_id="worker-log:0",
    )

    assert processed is True
    lines = _claim_lines(capsys.readouterr().out)
    assert len(lines) == 1
    line = lines[0]
    assert line["job_id"] == str(job_id)
    assert line["step"] == JobStep.SCORE.value
    assert line["worker_id"] == "worker-log:0"
    assert line["run_id"] == str(run_id)


async def test_an_empty_queue_logs_no_claim_line(
    connection: AsyncConnection, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_json_logging("INFO")

    async def unreachable(context: StepContext) -> None:
        raise AssertionError("no job was due; the handler must not run")

    processed = await process_next_job(
        _single_session_factory(connection),
        handlers={JobStep.SCORE: unreachable},
        settings=SETTINGS,
        clock=_clock,
        worker_id="worker-log:0",
    )

    assert processed is False
    assert _claim_lines(capsys.readouterr().out) == []


async def test_each_job_run_by_two_workers_appears_in_exactly_one_claim_line(
    database_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    engine_a = build_engine(database_url)
    engine_b = build_engine(database_url)
    handled: list[tuple[uuid.UUID, str]] = []

    async def handler(context: StepContext) -> None:
        assert context.sessions is not None
        async with context.sessions() as session:
            row = await session.get(Job, context.job.id)
            assert row is not None and row.locked_by is not None
            handled.append((context.job.id, row.locked_by))

    async with engine_a.begin() as setup:
        run_ids, job_ids = await setup.run_sync(lambda conn: _make_rescore_jobs(conn, 6))

    settings = SETTINGS.model_copy(update={"worker_concurrency": 2, "job_poll_interval_s": 0.02})
    stop = asyncio.Event()
    tasks = [
        run_job_loop(
            _session_factory(engine),
            handlers={JobStep.SCORE: handler},
            settings=settings,
            clock=_clock,
            worker_id=f"worker-{worker}:{loop_index}",
            stop=stop,
        )
        for worker, engine in enumerate((engine_a, engine_b))
        for loop_index in range(settings.worker_concurrency)
    ]
    configure_json_logging("INFO")
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, _stop_once_final(engine_a, job_ids, stop, 0.02)), timeout=15
        )
    finally:
        await _cleanup(engine_a, run_ids)
        await engine_a.dispose()
        await engine_b.dispose()

    claim_lines = _claim_lines(capsys.readouterr().out)
    by_job = {str(line["job_id"]): line for line in claim_lines}
    assert set(by_job) == {str(job_id) for job_id in job_ids}
    assert len(claim_lines) == len(job_ids)  # each job's job_id names exactly one claim line
    worker_of = {job_id: worker_id for job_id, worker_id in handled}
    for job_id_str, line in by_job.items():
        assert line["worker_id"] == worker_of[uuid.UUID(job_id_str)]
