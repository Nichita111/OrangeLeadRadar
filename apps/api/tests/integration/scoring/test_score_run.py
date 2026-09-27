"""Integration tests of the `SCORE` step's scope and of its place in the job loop
([Rescoring](/architecture/rules.md#rescoring) Triggers and Services, [Run lifecycle]
(/architecture/services/worker.md#run-lifecycle)): it scores the pairs its run names and leaves
the run's status, progress and end to the job loop."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from leadradar.core.enums import (
    AuditAction,
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunStatus,
    ScoringConfigStatus,
)
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.db.models.signals import AccountScore
from leadradar.worker.loop import process_next_job
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import STEP_HANDLERS
from leadradar.worker.steps.score import run_score_step
from tests.integration import factories as f
from tests.integration.pipeline_doubles import T0, Clock, session_factory

pytestmark = pytest.mark.integration

STARTED = datetime(2026, 9, 26, 11, 0, tzinfo=UTC)


@dataclass
class World:
    accounts: list[uuid.UUID]
    services: list[uuid.UUID]  # each with an ACTIVE scoring config


def _arrange(conn: Connection) -> World:
    accounts = [f.make_account(conn, name=f"Account {i}") for i in range(2)]
    services = [f.make_service(conn) for _ in range(2)]
    for service in services:
        f.make_scoring_config(conn, service, status=ScoringConfigStatus.ACTIVE, settings={})
    f.make_service(conn)  # a service without a scoring config
    return World(accounts, services)


@pytest.fixture
async def connection(async_connection: AsyncConnection) -> AsyncIterator[AsyncConnection]:
    await async_connection.execute(
        update(Job)
        .where(Job.status.in_((JobStatus.READY, JobStatus.RUNNING)))
        .values(status=JobStatus.CANCELLED)
    )
    yield async_connection


async def _scores(session: AsyncSession) -> set[tuple[uuid.UUID, uuid.UUID]]:
    rows = await session.execute(
        select(AccountScore.account_id, AccountScore.service_id).where(
            AccountScore.is_current.is_(True)
        )
    )
    return {(a, s) for a, s in rows}


async def _run_score(session: AsyncSession, run_id: uuid.UUID) -> None:
    run = await session.get(PipelineRun, run_id)
    assert run is not None
    await run_score_step(session, run=run, alert_max_age_days=14, now=T0)
    await session.flush()


async def test_a_refresh_scores_its_account_for_every_service_with_an_active_config(
    connection: AsyncConnection,
) -> None:
    world = await connection.run_sync(_arrange)
    run_id = await connection.run_sync(
        lambda c: f.make_pipeline_run(
            c,
            account_id=world.accounts[0],
            status=PipelineRunStatus.RUNNING,
            progress={"documents_fetched": 3},
            started_at=STARTED,
        )
    )
    async with session_factory(connection)() as session:
        await _run_score(session, run_id)

        assert await _scores(session) == {(world.accounts[0], s) for s in world.services}
        run = await session.get(PipelineRun, run_id)
        assert run is not None
        assert (run.status, run.progress, run.finished_at) == (
            PipelineRunStatus.RUNNING,
            {"documents_fetched": 3},
            None,
        )


async def test_a_rescore_scores_only_the_pairs_it_names_and_rerunning_writes_nothing(
    connection: AsyncConnection,
) -> None:
    world = await connection.run_sync(_arrange)
    pair, whole_service = await connection.run_sync(
        lambda c: (
            f.make_pipeline_run(
                c,
                kind=PipelineRunKind.RESCORE,
                account_id=world.accounts[0],
                service_id=world.services[0],
            ),
            f.make_pipeline_run(c, kind=PipelineRunKind.RESCORE, service_id=world.services[1]),
        )
    )
    async with session_factory(connection)() as session:
        await _run_score(session, pair)
        assert await _scores(session) == {(world.accounts[0], world.services[0])}

        await _run_score(session, whole_service)
        assert await _scores(session) == {
            (world.accounts[0], world.services[0]),
            (world.accounts[0], world.services[1]),
            (world.accounts[1], world.services[1]),
        }
        rows = await session.scalar(select(func.count()).select_from(AccountScore))

        await _run_score(session, pair)
        await _run_score(session, whole_service)
        assert await session.scalar(select(func.count()).select_from(AccountScore)) == rows


@pytest.mark.parametrize(("earlier_failure", "expected"), [(False, "SUCCEEDED"), (True, "PARTIAL")])
async def test_the_job_loop_settles_a_refresh_after_its_score_job(
    earlier_failure: bool, expected: str, connection: AsyncConnection
) -> None:
    world = await connection.run_sync(_arrange)
    errors = [{"stage": "FETCH", "code": "UPSTREAM_UNAVAILABLE", "message": "down"}]

    def build(conn: Connection) -> uuid.UUID:
        run = f.make_pipeline_run(
            conn,
            account_id=world.accounts[0],
            status=PipelineRunStatus.RUNNING,
            progress={"documents_fetched": 3},
            errors=errors if earlier_failure else [],
            started_at=STARTED,
        )
        if earlier_failure:
            f.make_job(conn, run, step=JobStep.FETCH, status=JobStatus.FAILED)
        f.make_job(conn, run, step=JobStep.SCORE, not_before=T0)
        return run

    run_id = await connection.run_sync(build)

    while await process_next_job(
        session_factory(connection),
        handlers={JobStep.SCORE: STEP_HANDLERS[JobStep.SCORE]},
        settings=WorkerSettings(database_url=SecretStr("postgresql://unused")),
        clock=Clock(),
        worker_id="worker-1",
    ):
        pass

    status, progress, finished_at = (
        await connection.execute(
            select(PipelineRun.status, PipelineRun.progress, PipelineRun.finished_at).where(
                PipelineRun.id == run_id
            )
        )
    ).one()
    assert status.value == expected
    assert progress == {"documents_fetched": 3}
    finished = await connection.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.run_id == run_id, AuditEvent.action == AuditAction.RUN_FINISHED)
    )
    assert finished == 1
    assert finished_at == T0
