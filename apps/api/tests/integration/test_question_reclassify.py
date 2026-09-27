"""Question changes enqueue reclassification in the configuration transaction."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.configuration.commands import create_question, create_service, update_question
from leadradar.core.enums import (
    AccountStatus,
    AuditAction,
    DocumentSourceType,
    JobStep,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
)
from leadradar.core.job_queue import job_priority
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.runs.enqueue import enqueue_reclassify
from tests.integration import factories

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 27, tzinfo=UTC)


async def _seed(
    session: AsyncSession, maker: Callable[..., uuid.UUID], **kwargs: object
) -> uuid.UUID:
    return await session.run_sync(lambda sync: maker(sync.connection(), **kwargs))


async def test_create_and_revision_enqueue_one_signal_job_per_active_account(
    async_session: AsyncSession,
) -> None:
    user_id = await _seed(async_session, factories.make_app_user)
    active_id = await _seed(async_session, factories.make_account)
    await _seed(async_session, factories.make_account, status=AccountStatus.INACTIVE)
    service = await create_service(
        async_session,
        code=f"SERVICE_{uuid.uuid4().hex[:8].upper()}",
        name=f"Service {uuid.uuid4().hex[:8]}",
        description="A service",
        value_proposition="A proposition",
        actor_id=user_id,
        now=NOW,
    )
    question = await create_question(
        async_session,
        service_id=service.id,
        key="NEW_SIGNAL",
        text="Does it have a new signal?",
        answer_type=SignalQuestionAnswerType.YES_NO,
        options=None,
        polarity=SignalQuestionPolarity.POSITIVE,
        source_types=[DocumentSourceType.NEWS],
        hint_terms=[],
        actor_id=user_id,
        now=NOW,
    )
    assert question.revision == 1 and question.run_id is not None
    run = await async_session.get(PipelineRun, question.run_id)
    assert run is not None
    assert (run.kind, run.trigger, run.status) == (
        PipelineRunKind.RECLASSIFY,
        PipelineRunTrigger.QUESTION_CHANGE,
        PipelineRunStatus.QUEUED,
    )
    assert (run.service_id, run.question_id, run.account_id, run.requested_by) == (
        service.id,
        question.id,
        None,
        user_id,
    )
    jobs = (await async_session.scalars(select(Job).where(Job.run_id == run.id))).all()
    assert len(jobs) == 1
    assert (jobs[0].step, jobs[0].payload, jobs[0].priority) == (
        JobStep.SIGNAL,
        {"account_id": str(active_id)},
        job_priority(PipelineRunKind.RECLASSIFY, PipelineRunTrigger.QUESTION_CHANGE),
    )
    audit = (
        await async_session.scalars(select(AuditEvent).where(AuditEvent.run_id == run.id))
    ).one()
    assert audit.action == AuditAction.RUN_REQUESTED.value

    changed = await update_question(
        async_session,
        question_id=question.id,
        text="Does it have a revised signal?",
        answer_type=None,
        options=None,
        source_types=None,
        hint_terms=None,
        status=None,
        actor_id=user_id,
        now=NOW,
    )
    assert changed.revision == 2 and changed.run_id not in (None, question.run_id)
    hints = await update_question(
        async_session,
        question_id=question.id,
        text=None,
        answer_type=None,
        options=None,
        source_types=None,
        hint_terms=["new"],
        status=None,
        actor_id=user_id,
        now=NOW,
    )
    assert hints.revision == 2 and hints.run_id is None
    deactivated = await update_question(
        async_session,
        question_id=question.id,
        text=None,
        answer_type=None,
        options=None,
        source_types=None,
        hint_terms=None,
        status=SignalQuestionStatus.INACTIVE,
        actor_id=user_id,
        now=NOW,
    )
    assert deactivated.run_id is None
    reactivated = await update_question(
        async_session,
        question_id=question.id,
        text=None,
        answer_type=None,
        options=None,
        source_types=None,
        hint_terms=None,
        status=SignalQuestionStatus.ACTIVE,
        actor_id=user_id,
        now=NOW,
    )
    assert reactivated.revision == 2 and reactivated.run_id is not None


async def test_reclassify_without_an_active_account_starts_with_score(
    async_session: AsyncSession,
) -> None:
    user_id = await _seed(async_session, factories.make_app_user)
    service_id = await _seed(async_session, factories.make_service)
    question_id = await _seed(async_session, factories.make_signal_question, service_id=service_id)
    run_id = await enqueue_reclassify(
        async_session,
        question_id=question_id,
        service_id=service_id,
        requested_by=user_id,
        now=NOW,
    )
    jobs = (await async_session.scalars(select(Job).where(Job.run_id == run_id))).all()
    assert [(job.step, job.payload) for job in jobs] == [(JobStep.SCORE, {})]
