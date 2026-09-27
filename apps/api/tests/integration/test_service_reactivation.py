"""Reactivating a service (`INACTIVE` to `ACTIVE`) reclassifies every `ACTIVE` question
([Services and questions](/architecture/interfaces.md#services-and-questions) `API-10`'s note,
`AC-02`)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.configuration.commands import (
    create_question,
    create_service,
    update_question,
    update_service,
)
from leadradar.core.enums import (
    AuditAction,
    DocumentSourceType,
    PipelineRunKind,
    PipelineRunTrigger,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
)
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.ingestion import PipelineRun
from tests.integration import factories

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 27, tzinfo=UTC)


async def _seed(
    session: AsyncSession, maker: Callable[..., uuid.UUID], **kwargs: object
) -> uuid.UUID:
    return await session.run_sync(lambda sync: maker(sync.connection(), **kwargs))


async def _run_count(session: AsyncSession, service_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(PipelineRun)
            .where(PipelineRun.service_id == service_id)
        )
    ).scalar_one()


async def test_reactivating_a_service_queues_one_reclassify_run_per_active_question(
    async_session: AsyncSession,
) -> None:
    user_id = await _seed(async_session, factories.make_app_user)
    service = await create_service(
        async_session,
        code=f"SERVICE_{uuid.uuid4().hex[:8].upper()}",
        name=f"Service {uuid.uuid4().hex[:8]}",
        description="A service",
        value_proposition="A proposition",
        actor_id=user_id,
        now=NOW,
    )
    active_question = await create_question(
        async_session,
        service_id=service.id,
        key="ACTIVE_ONE",
        text="Does it have a signal?",
        answer_type=SignalQuestionAnswerType.YES_NO,
        options=None,
        polarity=SignalQuestionPolarity.POSITIVE,
        source_types=[DocumentSourceType.NEWS],
        hint_terms=[],
        actor_id=user_id,
        now=NOW,
    )
    inactive_question = await create_question(
        async_session,
        service_id=service.id,
        key="INACTIVE_ONE",
        text="Does it have another signal?",
        answer_type=SignalQuestionAnswerType.YES_NO,
        options=None,
        polarity=SignalQuestionPolarity.POSITIVE,
        source_types=[DocumentSourceType.NEWS],
        hint_terms=[],
        actor_id=user_id,
        now=NOW,
    )
    await update_question(
        async_session,
        question_id=inactive_question.id,
        text=None,
        answer_type=None,
        options=None,
        source_types=None,
        hint_terms=None,
        status=SignalQuestionStatus.INACTIVE,
        actor_id=user_id,
        now=NOW,
    )
    await update_service(
        async_session,
        service_id=service.id,
        name=None,
        description=None,
        value_proposition=None,
        status=ServiceStatus.INACTIVE,
        actor_id=user_id,
        now=NOW,
    )
    runs_before_reactivation = await _run_count(async_session, service.id)

    await update_service(
        async_session,
        service_id=service.id,
        name=None,
        description=None,
        value_proposition=None,
        status=ServiceStatus.ACTIVE,
        actor_id=user_id,
        now=NOW,
    )

    assert await _run_count(async_session, service.id) == runs_before_reactivation + 1

    active_question_runs = (
        await async_session.scalars(
            select(PipelineRun).where(
                PipelineRun.question_id == active_question.id,
                PipelineRun.kind == PipelineRunKind.RECLASSIFY,
            )
        )
    ).all()
    assert len(active_question_runs) == 2
    new_run = next(run for run in active_question_runs if run.id != active_question.run_id)
    assert new_run.trigger == PipelineRunTrigger.QUESTION_CHANGE
    assert new_run.service_id == service.id

    inactive_question_runs = (
        await async_session.scalars(
            select(PipelineRun.id).where(PipelineRun.question_id == inactive_question.id)
        )
    ).all()
    assert len(inactive_question_runs) == 1

    audit = (
        await async_session.scalars(select(AuditEvent).where(AuditEvent.run_id == new_run.id))
    ).one()
    assert audit.action == AuditAction.RUN_REQUESTED.value


async def test_deactivating_or_resaving_the_same_status_queues_nothing(
    async_session: AsyncSession,
) -> None:
    user_id = await _seed(async_session, factories.make_app_user)
    service = await create_service(
        async_session,
        code=f"SERVICE_{uuid.uuid4().hex[:8].upper()}",
        name=f"Service {uuid.uuid4().hex[:8]}",
        description="A service",
        value_proposition="A proposition",
        actor_id=user_id,
        now=NOW,
    )
    await create_question(
        async_session,
        service_id=service.id,
        key="A_QUESTION",
        text="Does it have a signal?",
        answer_type=SignalQuestionAnswerType.YES_NO,
        options=None,
        polarity=SignalQuestionPolarity.POSITIVE,
        source_types=[DocumentSourceType.NEWS],
        hint_terms=[],
        actor_id=user_id,
        now=NOW,
    )
    runs_after_creation = await _run_count(async_session, service.id)

    await update_service(
        async_session,
        service_id=service.id,
        name=None,
        description=None,
        value_proposition=None,
        status=ServiceStatus.ACTIVE,
        actor_id=user_id,
        now=NOW,
    )
    assert await _run_count(async_session, service.id) == runs_after_creation

    await update_service(
        async_session,
        service_id=service.id,
        name=None,
        description=None,
        value_proposition=None,
        status=ServiceStatus.INACTIVE,
        actor_id=user_id,
        now=NOW,
    )
    assert await _run_count(async_session, service.id) == runs_after_creation


async def test_reactivating_a_service_without_active_questions_queues_nothing(
    async_session: AsyncSession,
) -> None:
    user_id = await _seed(async_session, factories.make_app_user)
    service = await create_service(
        async_session,
        code=f"SERVICE_{uuid.uuid4().hex[:8].upper()}",
        name=f"Service {uuid.uuid4().hex[:8]}",
        description="A service",
        value_proposition="A proposition",
        actor_id=user_id,
        now=NOW,
    )
    await update_service(
        async_session,
        service_id=service.id,
        name=None,
        description=None,
        value_proposition=None,
        status=ServiceStatus.INACTIVE,
        actor_id=user_id,
        now=NOW,
    )

    await update_service(
        async_session,
        service_id=service.id,
        name=None,
        description=None,
        value_proposition=None,
        status=ServiceStatus.ACTIVE,
        actor_id=user_id,
        now=NOW,
    )

    assert await _run_count(async_session, service.id) == 0
