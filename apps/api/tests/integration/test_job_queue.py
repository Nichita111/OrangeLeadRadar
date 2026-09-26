"""Integration tests of the worker's job loop and the run commands against a real database
([Job queue](/architecture/services/worker.md#job-queue),
[Run lifecycle](/architecture/services/worker.md#run-lifecycle); `S-PIP-01`, `S-PIP-03`,
`S-PIP-04`, `N-05`).

Every test runs in one outer transaction rolled back at the end; the loop's own transactions are
savepoints inside it. Jobs other tests committed are cancelled inside that transaction first, so
the loop only ever claims this test's jobs."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from leadradar.core.enums import (
    AccountStatus,
    AppUserRole,
    AuditAction,
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunStage,
    PipelineRunStatus,
    PipelineRunTrigger,
    SourcePluginCode,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Job, PipelineRun, PluginUsage, SourcePlugin
from leadradar.runs.commands import cancel_run, request_account_refresh
from leadradar.runs.errors import AccountInactive, RunFinished
from leadradar.worker.loop import process_next_job
from leadradar.worker.queue import claim_next_job
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import StepContext, StepFailed, StepHandler
from tests.integration import factories as f

pytestmark = pytest.mark.integration

T0 = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
SETTINGS = WorkerSettings(database_url=SecretStr("postgresql://unused"))


class Clock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


async def _succeed(context: StepContext) -> None:
    return None


@pytest.fixture
async def connection(async_connection: AsyncConnection) -> AsyncIterator[AsyncConnection]:
    await async_connection.execute(
        update(Job)
        .where(Job.status.in_((JobStatus.READY, JobStatus.RUNNING)))
        .values(status=JobStatus.CANCELLED)
    )
    yield async_connection


def _session_factory(connection: AsyncConnection) -> Callable[[], AsyncSession]:
    def make() -> AsyncSession:
        return AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    return make


async def _process(
    connection: AsyncConnection,
    handlers: dict[JobStep, StepHandler],
    clock: Clock,
    settings: WorkerSettings = SETTINGS,
    worker_id: str = "worker-1",
) -> bool:
    return await process_next_job(
        _session_factory(connection),
        handlers=handlers,
        settings=settings,
        clock=clock,
        worker_id=worker_id,
    )


async def _insert(connection: AsyncConnection, build: Callable[[Connection], Any]) -> Any:
    return await connection.run_sync(build)


async def _run(connection: AsyncConnection, run_id: uuid.UUID) -> Any:
    return (await connection.execute(select(PipelineRun).where(PipelineRun.id == run_id))).one()


async def _jobs(connection: AsyncConnection, run_id: uuid.UUID) -> list[Any]:
    return list(
        (
            await connection.execute(
                select(Job).where(Job.run_id == run_id).order_by(Job.created_at, Job.step)
            )
        ).all()
    )


async def _audit_actions(connection: AsyncConnection, run_id: uuid.UUID) -> list[str]:
    rows = await connection.execute(
        select(AuditEvent.action).where(AuditEvent.run_id == run_id).order_by(AuditEvent.id)
    )
    return sorted(rows.scalars())


def _rescore_run(conn: Connection) -> uuid.UUID:
    account_id = f.make_account(conn)
    service_id = f.make_service(conn)
    run_id = f.make_pipeline_run(
        conn,
        kind=PipelineRunKind.RESCORE,
        trigger=PipelineRunTrigger.FEEDBACK,
        account_id=account_id,
        service_id=service_id,
    )
    f.make_job(conn, run_id, step=JobStep.SCORE, not_before=T0)
    return run_id


async def test_a_claimed_job_completes_and_its_run_succeeds(connection: AsyncConnection) -> None:
    run_id = await _insert(connection, _rescore_run)

    assert await _process(connection, {JobStep.SCORE: _succeed}, Clock()) is True

    run = await _run(connection, run_id)
    assert run.status is PipelineRunStatus.SUCCEEDED
    assert run.stage is None
    assert run.started_at == T0
    assert run.finished_at == T0
    [job] = await _jobs(connection, run_id)
    assert (job.status, job.attempts, job.locked_by) == (JobStatus.DONE, 1, None)
    assert await _audit_actions(connection, run_id) == [AuditAction.RUN_FINISHED]
    assert await _process(connection, {JobStep.SCORE: _succeed}, Clock()) is False


async def test_a_failed_plugin_makes_the_refresh_partial_and_it_is_still_scored(
    connection: AsyncConnection,
) -> None:
    def build(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        account_id = f.make_account(conn)
        run_id = f.make_pipeline_run(conn, account_id=account_id)
        for code in (SourcePluginCode.GDELT, SourcePluginCode.RSS):
            f.make_job(
                conn, run_id, step=JobStep.FETCH, payload={"plugin_code": code}, not_before=T0
            )
        return account_id, run_id

    account_id, run_id = await _insert(connection, build)
    stages: list[PipelineRunStage | None] = []

    async def fetch(context: StepContext) -> None:
        run = await context.session.get(PipelineRun, context.job.run_id)
        assert run is not None
        stages.append(run.stage)
        if context.job.payload["plugin_code"] == "GDELT":
            raise StepFailed("UPSTREAM_UNAVAILABLE", "GDELT answered 503.")

    handlers: dict[JobStep, StepHandler] = {JobStep.FETCH: fetch, JobStep.SCORE: _succeed}
    settings = SETTINGS.model_copy(update={"job_max_attempts": 1})
    clock = Clock()
    while await _process(connection, handlers, clock, settings):
        pass

    run = await _run(connection, run_id)
    assert run.status is PipelineRunStatus.PARTIAL
    assert run.errors == [
        {
            "stage": "FETCH",
            "plugin_code": "GDELT",
            "code": "UPSTREAM_UNAVAILABLE",
            "message": "GDELT answered 503.",
        }
    ]
    assert stages == [PipelineRunStage.FETCH, PipelineRunStage.FETCH]
    jobs = await _jobs(connection, run_id)
    assert sorted((job.step, job.status) for job in jobs) == sorted(
        [
            (JobStep.FETCH, JobStatus.FAILED),
            (JobStep.FETCH, JobStatus.DONE),
            (JobStep.SCORE, JobStatus.DONE),
        ]
    )
    account = (await connection.execute(select(Account).where(Account.id == account_id))).one()
    assert account.last_refreshed_at == T0
    assert account.next_refresh_at == T0 + timedelta(hours=SETTINGS.refresh_interval_hours)


async def test_a_failing_step_is_retried_with_backoff_then_fails_its_run(
    connection: AsyncConnection,
) -> None:
    run_id = await _insert(connection, _rescore_run)

    async def broken(context: StepContext) -> None:
        raise RuntimeError("embedder down")

    handlers: dict[JobStep, StepHandler] = {JobStep.SCORE: broken}
    clock = Clock()

    assert await _process(connection, handlers, clock) is True
    [job] = await _jobs(connection, run_id)
    assert (job.status, job.attempts, job.last_error) == (JobStatus.READY, 1, "embedder down")
    assert job.not_before == T0 + timedelta(seconds=SETTINGS.job_retry_backoff_s)

    clock.now = job.not_before - timedelta(seconds=1)
    assert await _process(connection, handlers, clock) is False

    clock.now = job.not_before
    assert await _process(connection, handlers, clock) is True
    [job] = await _jobs(connection, run_id)
    assert job.not_before == clock.now + timedelta(seconds=2 * SETTINGS.job_retry_backoff_s)

    clock.now = job.not_before
    assert await _process(connection, handlers, clock) is True
    [job] = await _jobs(connection, run_id)
    assert (job.status, job.attempts) == (JobStatus.FAILED, SETTINGS.job_max_attempts)
    run = await _run(connection, run_id)
    assert run.status is PipelineRunStatus.FAILED
    assert run.errors == [{"stage": "SCORE", "code": "INTERNAL", "message": "embedder down"}]


async def test_a_step_without_a_handler_fails_at_once(connection: AsyncConnection) -> None:
    run_id = await _insert(connection, _rescore_run)

    assert await _process(connection, {}, Clock()) is True

    [job] = await _jobs(connection, run_id)
    assert (job.status, job.attempts) == (JobStatus.FAILED, 1)
    assert job.last_error == "The worker has no handler for step SCORE."
    assert (await _run(connection, run_id)).status is PipelineRunStatus.FAILED


async def test_a_job_abandoned_beyond_the_lock_timeout_is_reclaimed_and_completes(
    connection: AsyncConnection,
) -> None:
    def build(conn: Connection) -> uuid.UUID:
        run_id = f.make_pipeline_run(
            conn,
            kind=PipelineRunKind.RESCORE,
            status=PipelineRunStatus.RUNNING,
            stage=PipelineRunStage.SCORE,
            started_at=T0,
        )
        f.make_job(
            conn,
            run_id,
            status=JobStatus.RUNNING,
            attempts=1,
            locked_by="stopped-worker",
            locked_at=T0,
            not_before=T0,
        )
        return run_id

    run_id = await _insert(connection, build)
    clock = Clock()

    clock.now = T0 + timedelta(seconds=SETTINGS.job_lock_timeout_s)
    assert await _process(connection, {JobStep.SCORE: _succeed}, clock) is False

    clock.now = T0 + timedelta(seconds=SETTINGS.job_lock_timeout_s + 1)
    assert await _process(connection, {JobStep.SCORE: _succeed}, clock) is True
    [job] = await _jobs(connection, run_id)
    assert (job.status, job.attempts) == (JobStatus.DONE, 2)
    assert (await _run(connection, run_id)).status is PipelineRunStatus.SUCCEEDED


async def test_a_cancelled_run_never_runs_its_ready_jobs(connection: AsyncConnection) -> None:
    def build(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        user_id = f.make_app_user(conn, role=AppUserRole.SALES)
        account_id = f.make_account(conn)
        run_id = f.make_pipeline_run(conn, account_id=account_id, requested_by=user_id)
        f.make_job(conn, run_id, step=JobStep.FETCH, payload={"plugin_code": "GDELT"})
        return user_id, run_id

    user_id, run_id = await _insert(connection, build)
    principal = AppUser(id=user_id, display_name="Sales", role=AppUserRole.SALES)
    session = _session_factory(connection)()

    view = await cancel_run(session, run_id=run_id, principal=principal, now=T0)

    assert view.status is PipelineRunStatus.CANCELLED
    assert view.finished_at == T0
    [job] = await _jobs(connection, run_id)
    assert job.status is JobStatus.CANCELLED
    assert await _audit_actions(connection, run_id) == [AuditAction.RUN_CANCELLED]
    assert await _process(connection, {JobStep.FETCH: _succeed}, Clock()) is False
    with pytest.raises(RunFinished):
        await cancel_run(session, run_id=run_id, principal=principal, now=T0)

    # A job enqueued by a step that was running when the run was cancelled is cancelled too.
    await _insert(
        connection, lambda conn: f.make_job(conn, run_id, step=JobStep.PROCESS, not_before=T0)
    )
    assert await _process(connection, {JobStep.PROCESS: _succeed}, Clock()) is False
    assert {job.status for job in await _jobs(connection, run_id)} == {JobStatus.CANCELLED}


async def test_concurrent_claims_never_take_the_same_job(async_engine: AsyncEngine) -> None:
    def build(conn: Connection) -> tuple[list[uuid.UUID], set[uuid.UUID]]:
        # Two runs, so neither claim waits on the other's run lock; priority -1 puts both jobs
        # ahead of every job other tests left in the shared database.
        runs = [f.make_pipeline_run(conn, kind=PipelineRunKind.RESCORE) for _ in range(2)]
        return runs, {f.make_job(conn, run, priority=-1) for run in runs}

    async with async_engine.begin() as setup:
        run_ids, job_ids = await setup.run_sync(build)
    try:
        async with (
            AsyncSession(async_engine) as first,
            AsyncSession(async_engine) as second,
            first.begin(),
            second.begin(),
        ):
            one = await claim_next_job(first, worker_id="a", now=datetime.now(tz=UTC))
            two = await claim_next_job(second, worker_id="b", now=datetime.now(tz=UTC))
            assert one is not None and two is not None
            assert {one.id, two.id} == job_ids
            await first.rollback()
            await second.rollback()
    finally:
        async with async_engine.begin() as cleanup:
            await cleanup.execute(delete(Job).where(Job.run_id.in_(run_ids)))
            await cleanup.execute(delete(PipelineRun).where(PipelineRun.id.in_(run_ids)))


async def test_a_refresh_is_enqueued_once_with_one_fetch_per_available_plugin(
    connection: AsyncConnection,
) -> None:
    await connection.execute(delete(PluginUsage))
    await connection.execute(delete(SourcePlugin))

    def build(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        f.make_source_plugin(conn, code=SourcePluginCode.GDELT)
        f.make_source_plugin(conn, code=SourcePluginCode.RSS, enabled=False)
        f.make_source_plugin(conn, code=SourcePluginCode.CRUNCHBASE)
        f.make_source_plugin(conn, code=SourcePluginCode.WEBSITE, daily_quota=5)
        conn.execute(
            insert(PluginUsage).values(
                plugin_code=SourcePluginCode.WEBSITE, day=T0.date(), requests=5
            )
        )
        return f.make_app_user(conn), f.make_account(conn)

    user_id, account_id = await _insert(connection, build)
    principal = AppUser(id=user_id, display_name="Sales", role=AppUserRole.SALES)
    session = _session_factory(connection)()

    first = await request_account_refresh(
        session, account_id=account_id, principal=principal, keys_configured=(), now=T0
    )
    second = await request_account_refresh(
        session, account_id=account_id, principal=principal, keys_configured=(), now=T0
    )

    assert first.created is True
    assert second.created is False
    assert second.run.id == first.run.id
    assert first.run.status is PipelineRunStatus.QUEUED
    assert first.run.requested_by_name == "Test User"
    jobs = await _jobs(connection, first.run.id)
    assert [(job.step, job.payload, job.priority) for job in jobs] == [
        (JobStep.FETCH, {"plugin_code": "GDELT"}, 1)
    ]
    assert await _audit_actions(connection, first.run.id) == [AuditAction.RUN_REQUESTED]


async def test_a_refresh_with_no_available_plugin_starts_with_its_score_job(
    connection: AsyncConnection,
) -> None:
    await connection.execute(delete(PluginUsage))
    await connection.execute(delete(SourcePlugin))
    user_id, account_id = await _insert(
        connection, lambda conn: (f.make_app_user(conn), f.make_account(conn))
    )
    principal = AppUser(id=user_id, display_name="Sales", role=AppUserRole.SALES)

    result = await request_account_refresh(
        _session_factory(connection)(),
        account_id=account_id,
        principal=principal,
        keys_configured=(),
        now=T0,
    )

    assert [job.step for job in await _jobs(connection, result.run.id)] == [JobStep.SCORE]


async def test_an_inactive_account_is_not_refreshed(connection: AsyncConnection) -> None:
    user_id, account_id = await _insert(
        connection,
        lambda conn: (f.make_app_user(conn), f.make_account(conn, status=AccountStatus.INACTIVE)),
    )
    principal = AppUser(id=user_id, display_name="Sales", role=AppUserRole.SALES)

    with pytest.raises(AccountInactive):
        await request_account_refresh(
            _session_factory(connection)(),
            account_id=account_id,
            principal=principal,
            keys_configured=(),
            now=T0,
        )
