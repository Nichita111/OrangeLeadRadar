"""Integration tests of [Impact](/architecture/rules.md#impact)'s capability function,
`evaluation.impact.read_impact`, against a real database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from leadradar.core.enums import (
    AuditEventKind,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
)
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.feedback import EvaluationResult
from leadradar.db.models.ingestion import PipelineRun
from leadradar.evaluation.impact import read_impact
from leadradar.settings import ApiSettings
from tests.integration import factories as f

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 15, tzinfo=UTC)
PERIOD_DAYS = 30


def _settings(api_settings: ApiSettings, **overrides: int) -> ApiSettings:
    return api_settings.model_copy(
        update={
            "impact_period_days": PERIOD_DAYS,
            "manual_research_minutes_per_account": 120,
            **overrides,
        }
    )


async def _make_run(
    connection: AsyncConnection,
    *,
    kind: PipelineRunKind = PipelineRunKind.ACCOUNT_REFRESH,
    status: PipelineRunStatus = PipelineRunStatus.SUCCEEDED,
    account_id: uuid.UUID | None = None,
    started_at: datetime,
    finished_at: datetime,
) -> uuid.UUID:
    def _insert(conn: Connection) -> uuid.UUID:
        account = account_id
        if kind == PipelineRunKind.ACCOUNT_REFRESH and account is None:
            account = f.make_account(conn)
        return f.make_pipeline_run(
            conn,
            kind=kind,
            trigger=PipelineRunTrigger.SCHEDULE,
            account_id=account,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
        )

    return await connection.run_sync(_insert)


async def test_only_account_refresh_counts(
    async_connection: AsyncConnection, async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    finished = NOW - timedelta(days=1)
    started = finished - timedelta(minutes=10)
    for kind in (
        PipelineRunKind.RESCORE,
        PipelineRunKind.RECLASSIFY,
        PipelineRunKind.DISCOVERY,
        PipelineRunKind.EVALUATION,
    ):
        await _make_run(async_connection, kind=kind, started_at=started, finished_at=finished)

    report = await read_impact(async_session, _settings(api_settings), NOW)

    assert report.refreshes == 0
    assert report.accounts_refreshed == 0


async def test_only_succeeded_and_partial_count(
    async_connection: AsyncConnection, async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    finished = NOW - timedelta(days=1)
    started = finished - timedelta(minutes=10)
    for status in (
        PipelineRunStatus.QUEUED,
        PipelineRunStatus.RUNNING,
        PipelineRunStatus.FAILED,
        PipelineRunStatus.CANCELLED,
    ):
        await _make_run(async_connection, status=status, started_at=started, finished_at=finished)

    report = await read_impact(async_session, _settings(api_settings), NOW)

    assert report.refreshes == 0
    assert report.accounts_refreshed == 0


async def test_window_boundary_includes_exactly_period_days_and_excludes_a_second_earlier(
    async_connection: AsyncConnection, async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    on_boundary = NOW - timedelta(days=PERIOD_DAYS)
    just_outside = on_boundary - timedelta(seconds=1)
    await _make_run(
        async_connection, started_at=on_boundary - timedelta(minutes=5), finished_at=on_boundary
    )
    await _make_run(
        async_connection,
        started_at=just_outside - timedelta(minutes=5),
        finished_at=just_outside,
    )

    report = await read_impact(async_session, _settings(api_settings), NOW)

    assert report.refreshes == 1
    assert report.accounts_refreshed == 1


async def test_only_ai_call_rows_of_counted_runs_add_cost(
    async_connection: AsyncConnection, async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    finished = NOW - timedelta(days=1)
    started = finished - timedelta(minutes=10)
    counted_run = await _make_run(async_connection, started_at=started, finished_at=finished)

    older_finished = NOW - timedelta(days=PERIOD_DAYS + 5)
    older_run = await _make_run(
        async_connection,
        started_at=older_finished - timedelta(minutes=10),
        finished_at=older_finished,
    )

    def _insert_events(conn: Connection) -> None:
        f.make_audit_event(
            conn,
            kind=AuditEventKind.AI_CALL,
            action="AI_CALL",
            run_id=counted_run,
            payload={"cost_eur": 2.5},
        )
        f.make_audit_event(
            conn,
            kind=AuditEventKind.AI_CALL,
            action="AI_CALL",
            run_id=older_run,
            payload={"cost_eur": 100.0},
        )
        f.make_audit_event(conn, kind=AuditEventKind.RUN, action="RUN_STARTED", run_id=counted_run)

    await async_connection.run_sync(_insert_events)

    report = await read_impact(async_session, _settings(api_settings), NOW)

    assert report.cost_per_refresh_eur == pytest.approx(2.5)


async def test_findings_created_counts_only_findings_of_counted_runs(
    async_connection: AsyncConnection, async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    finished = NOW - timedelta(days=1)
    started = finished - timedelta(minutes=10)
    counted_run = await _make_run(async_connection, started_at=started, finished_at=finished)

    older_finished = NOW - timedelta(days=PERIOD_DAYS + 5)
    older_run = await _make_run(
        async_connection,
        started_at=older_finished - timedelta(minutes=10),
        finished_at=older_finished,
    )

    def _insert_findings(conn: Connection) -> None:
        service_id = f.make_service(conn)
        question_id = f.make_signal_question(conn, service_id)
        account_id = f.make_account(conn)
        source_plugin = f.make_source_plugin(conn)
        document_id = f.make_document(conn, counted_run)
        chunk_id = f.make_chunk(conn, document_id)

        counted_classification = f.make_classification(conn, chunk_id, question_id, counted_run)
        f.make_finding(conn, account_id, question_id, counted_classification, chunk_id)

        older_document_id = f.make_document(conn, older_run)
        older_chunk_id = f.make_chunk(conn, older_document_id)
        older_classification = f.make_classification(conn, older_chunk_id, question_id, older_run)
        f.make_finding(conn, account_id, question_id, older_classification, older_chunk_id)
        del source_plugin

    await async_connection.run_sync(_insert_findings)

    report = await read_impact(async_session, _settings(api_settings), NOW)

    assert report.findings_created == 1


async def test_latest_passing_evaluation_supplies_precision_and_labelled_items(
    async_connection: AsyncConnection, async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    def _insert_results(conn: Connection) -> None:
        older_passing_run = f.make_pipeline_run(
            conn,
            kind=PipelineRunKind.EVALUATION,
            status=PipelineRunStatus.SUCCEEDED,
            started_at=NOW - timedelta(days=10),
            finished_at=NOW - timedelta(days=10),
        )
        f.make_evaluation_result(
            conn,
            older_passing_run,
            passed=True,
            items=10,
            metrics={"precision": 0.5},
            created_at=NOW - timedelta(days=10),
        )

        latest_passing_run = f.make_pipeline_run(
            conn,
            kind=PipelineRunKind.EVALUATION,
            status=PipelineRunStatus.SUCCEEDED,
            started_at=NOW - timedelta(days=5),
            finished_at=NOW - timedelta(days=5),
        )
        f.make_evaluation_result(
            conn,
            latest_passing_run,
            passed=True,
            items=99,
            metrics={"precision": 0.99},
            created_at=NOW - timedelta(days=5),
        )

        newest_failing_run = f.make_pipeline_run(
            conn,
            kind=PipelineRunKind.EVALUATION,
            status=PipelineRunStatus.FAILED,
            started_at=NOW - timedelta(days=1),
            finished_at=NOW - timedelta(days=1),
        )
        f.make_evaluation_result(
            conn,
            newest_failing_run,
            passed=False,
            items=1000,
            metrics={"precision": 0.01},
            created_at=NOW - timedelta(days=1),
        )

    await async_connection.run_sync(_insert_results)

    report = await read_impact(async_session, _settings(api_settings), NOW)

    assert report.precision == pytest.approx(0.99)
    assert report.labelled_items == 99


async def test_reading_the_report_twice_writes_nothing(
    async_connection: AsyncConnection, async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    finished = NOW - timedelta(days=1)
    started = finished - timedelta(minutes=10)
    await _make_run(async_connection, started_at=started, finished_at=finished)

    async def _count(model: type, conn: AsyncConnection) -> int:
        result = await conn.execute(select(func.count()).select_from(model))
        return result.scalar_one()

    audit_before = await _count(AuditEvent, async_connection)
    evaluation_before = await _count(EvaluationResult, async_connection)
    runs_before = await _count(PipelineRun, async_connection)

    settings = _settings(api_settings)
    await read_impact(async_session, settings, NOW)
    await read_impact(async_session, settings, NOW)

    audit_after = await _count(AuditEvent, async_connection)
    evaluation_after = await _count(EvaluationResult, async_connection)
    runs_after = await _count(PipelineRun, async_connection)

    assert audit_after == audit_before
    assert runs_after == runs_before
    assert evaluation_after == evaluation_before
