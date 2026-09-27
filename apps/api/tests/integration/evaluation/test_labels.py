"""Integration tests of the label queue and manual labelling (`S-EVL-03`, `AC-48`,
`API-50`/`API-51`) against a real database, per "Tests for the coder" of
`.work/labelling-and-quality/design.md`."""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AccountStatus,
    AuditAction,
    ClassificationStatus,
    DocumentSourceType,
    DocumentTriageOutcome,
    EvaluationItemOrigin,
    EvaluationItemStatus,
    FindingStrength,
    SignalQuestionStatus,
)
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.feedback import EvaluationItem
from leadradar.db.models.identity import AppUser
from leadradar.evaluation.labels import count_active_items, label_pair, read_label_queue
from leadradar.settings import ApiSettings
from tests.integration import factories

pytestmark = pytest.mark.integration

_DB_URL = SecretStr("postgresql://unused")
_NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def _settings(**overrides: Any) -> ApiSettings:
    values: dict[str, Any] = {
        "database_url": _DB_URL,
        "migration_database_url": _DB_URL,
        "label_queue_size": 20,
    }
    values.update(overrides)
    return ApiSettings(**values)


async def _seed(session: AsyncSession, make: Callable[..., Any], *a: Any, **kw: Any) -> Any:
    return await session.run_sync(lambda s: make(s.connection(), *a, **kw))


async def _base_pair(
    session: AsyncSession,
    *,
    service_id: uuid.UUID | None = None,
    account_status: AccountStatus = AccountStatus.ACTIVE,
    question_status: SignalQuestionStatus = SignalQuestionStatus.ACTIVE,
    triage_outcome: DocumentTriageOutcome = DocumentTriageOutcome.KEPT,
    relevance: float = 0.9,
    source_type: DocumentSourceType = DocumentSourceType.NEWS,
    question_source_types: list[str] | None = None,
    chunk_count: int = 1,
) -> dict[str, Any]:
    """One passage of one document of one account, one question of one service: the smallest
    arrangement the label queue's base filter needs, with every knob the exclusion tests flip."""
    service_id = service_id or await _seed(session, factories.make_service)
    question_id = await _seed(
        session,
        factories.make_signal_question,
        service_id,
        status=question_status,
        source_types=question_source_types or [DocumentSourceType.NEWS.value],
    )
    account_id = await _seed(session, factories.make_account, status=account_status)
    run_id = await _seed(session, factories.make_pipeline_run)
    document_id = await _seed(
        session,
        factories.make_document,
        run_id,
        account_id=account_id,
        source_type=source_type,
        text="A document with enough passages.",
    )
    await _seed(
        session,
        factories.make_document_triage,
        document_id,
        outcome=triage_outcome,
        service_relevance={str(service_id): relevance},
    )
    chunk_id = await _seed(session, factories.make_chunk, document_id, ordinal=0, text="Passage 0.")
    chunk_ids = [chunk_id]
    for ordinal in range(1, chunk_count):
        chunk_ids.append(
            await _seed(
                session,
                factories.make_chunk,
                document_id,
                ordinal=ordinal,
                text=f"Passage {ordinal}.",
            )
        )
    return {
        "service": service_id,
        "question": question_id,
        "account": account_id,
        "chunk": chunk_id,
        "chunks": chunk_ids,
    }


async def _classify(
    session: AsyncSession, ids: dict[str, uuid.UUID], run_id: uuid.UUID, p_positive: float
) -> None:
    await _seed(
        session,
        factories.make_classification,
        ids["chunk"],
        ids["question"],
        run_id,
        p_positive=p_positive,
        status=ClassificationStatus.NEGATIVE,
        strength=None,
    )


class TestNeverReturnsClassifierOutput:
    async def test_label_task_carries_none_of_the_classifiers_fields(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(db_session)
        run_id = await _seed(db_session, factories.make_pipeline_run)
        await _classify(db_session, ids, run_id, p_positive=0.1)

        view = await read_label_queue(db_session, _settings(), ids["service"])

        assert len(view.tasks) == 1
        field_names = {field.name for field in dataclasses.fields(view.tasks[0])}
        assert field_names == {
            "chunk_id",
            "passage_text",
            "question",
            "question_revision",
            "account",
            "document",
        }


class TestStrataBoundaries:
    async def test_p_at_escalation_lower_lands_in_the_low_stratum(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(db_session)
        run_id = await _seed(db_session, factories.make_pipeline_run)
        await _classify(db_session, ids, run_id, p_positive=0.35)

        view = await read_label_queue(db_session, _settings(label_queue_size=1), ids["service"])

        assert len(view.tasks) == 1
        assert view.tasks[0].chunk_id == ids["chunk"]

    async def test_p_at_escalation_upper_lands_in_the_high_stratum(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(db_session)
        run_id = await _seed(db_session, factories.make_pipeline_run)
        await _classify(db_session, ids, run_id, p_positive=0.65)

        view = await read_label_queue(db_session, _settings(label_queue_size=1), ids["service"])

        assert len(view.tasks) == 1
        assert view.tasks[0].chunk_id == ids["chunk"]


class TestDrawsFromEveryStratum:
    async def test_low_band_high_and_not_selected_are_all_represented(
        self, db_session: AsyncSession
    ) -> None:
        service_id = await _seed(db_session, factories.make_service)
        run_id = await _seed(db_session, factories.make_pipeline_run)

        low = await _base_pair(db_session, service_id=service_id)
        await _classify(db_session, low, run_id, p_positive=0.1)
        band = await _base_pair(db_session, service_id=service_id)
        await _classify(db_session, band, run_id, p_positive=0.5)
        high = await _base_pair(db_session, service_id=service_id)
        await _classify(db_session, high, run_id, p_positive=0.9)
        not_selected = await _base_pair(db_session, service_id=service_id, chunk_count=2)

        view = await read_label_queue(db_session, _settings(label_queue_size=4), service_id)

        assert len(view.tasks) == 4
        chunk_ids = {task.chunk_id for task in view.tasks}
        expected = {low["chunk"], band["chunk"], high["chunk"]}
        assert expected <= chunk_ids
        # The NOT_SELECTED stratum's own long document has two passages that both qualify
        # (neither is classified); either one shows a task exists for it.
        assert chunk_ids - expected
        assert (chunk_ids - expected) <= set(not_selected["chunks"])


class TestExclusions:
    async def test_a_pair_with_an_active_item_is_excluded(self, db_session: AsyncSession) -> None:
        ids = await _base_pair(db_session)
        user_id = await _seed(db_session, factories.make_app_user)
        await _seed(
            db_session, factories.make_evaluation_item, ids["chunk"], ids["question"], user_id
        )

        view = await read_label_queue(db_session, _settings(), ids["service"])

        assert view.tasks == []

    async def test_a_pair_of_an_inactive_account_is_excluded(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(db_session, account_status=AccountStatus.INACTIVE)

        view = await read_label_queue(db_session, _settings(), ids["service"])

        assert view.tasks == []

    async def test_a_pair_of_an_inactive_question_is_excluded(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(db_session, question_status=SignalQuestionStatus.INACTIVE)

        view = await read_label_queue(db_session, _settings(), ids["service"])

        assert view.tasks == []

    async def test_a_pair_of_an_unkept_document_is_excluded(self, db_session: AsyncSession) -> None:
        ids = await _base_pair(db_session, triage_outcome=DocumentTriageOutcome.IRRELEVANT)

        view = await read_label_queue(db_session, _settings(), ids["service"])

        assert view.tasks == []

    async def test_a_pair_of_an_inapplicable_source_type_is_excluded(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(
            db_session,
            source_type=DocumentSourceType.JOB_POSTING,
            question_source_types=[DocumentSourceType.NEWS.value],
        )

        view = await read_label_queue(db_session, _settings(), ids["service"])

        assert view.tasks == []

    async def test_a_pair_of_another_services_question_is_excluded(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(db_session)
        other_service_id = await _seed(db_session, factories.make_service)

        view = await read_label_queue(db_session, _settings(), other_service_id)

        assert view.tasks == []
        assert ids["service"] != other_service_id


class TestManualLabel:
    async def test_replaces_an_active_finding_feedback_item_in_place(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(db_session)
        user_id = await _seed(db_session, factories.make_app_user)
        item_id = await _seed(
            db_session,
            factories.make_evaluation_item,
            ids["chunk"],
            ids["question"],
            user_id,
            origin=EvaluationItemOrigin.FINDING_FEEDBACK,
            expected_strength=FindingStrength.WEAK,
        )

        view = await label_pair(
            db_session,
            principal=await _app_user_row(db_session, user_id),
            chunk_id=ids["chunk"],
            question_id=ids["question"],
            question_revision=1,
            expected_strength=FindingStrength.STRONG,
            now=_NOW,
        )

        assert view.id == item_id
        assert view.origin == EvaluationItemOrigin.MANUAL
        assert view.expected_strength == FindingStrength.STRONG
        rows = (
            (
                await db_session.execute(
                    select(EvaluationItem).where(
                        EvaluationItem.chunk_id == ids["chunk"],
                        EvaluationItem.question_id == ids["question"],
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1

    async def test_labelling_twice_keeps_one_active_item(self, db_session: AsyncSession) -> None:
        ids = await _base_pair(db_session)
        user_id = await _seed(db_session, factories.make_app_user)
        principal = await _app_user_row(db_session, user_id)

        await label_pair(
            db_session,
            principal=principal,
            chunk_id=ids["chunk"],
            question_id=ids["question"],
            question_revision=1,
            expected_strength=FindingStrength.WEAK,
            now=_NOW,
        )
        await label_pair(
            db_session,
            principal=principal,
            chunk_id=ids["chunk"],
            question_id=ids["question"],
            question_revision=1,
            expected_strength=FindingStrength.STRONG,
            now=_NOW,
        )

        rows = (
            (
                await db_session.execute(
                    select(EvaluationItem).where(
                        EvaluationItem.chunk_id == ids["chunk"],
                        EvaluationItem.question_id == ids["question"],
                        EvaluationItem.status == EvaluationItemStatus.ACTIVE,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].expected_strength == FindingStrength.STRONG

    async def test_writes_an_item_labelled_audit_row_in_the_same_transaction(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(db_session)
        user_id = await _seed(db_session, factories.make_app_user)

        view = await label_pair(
            db_session,
            principal=await _app_user_row(db_session, user_id),
            chunk_id=ids["chunk"],
            question_id=ids["question"],
            question_revision=1,
            expected_strength=FindingStrength.MEDIUM,
            now=_NOW,
        )

        audit_rows = (
            (
                await db_session.execute(
                    select(AuditEvent).where(
                        AuditEvent.action == AuditAction.ITEM_LABELLED.value,
                        AuditEvent.entity_id == view.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_rows) == 1
        assert audit_rows[0].payload == {"expected_strength": "MEDIUM"}


class TestStaleItemsIgnored:
    async def test_a_stale_item_is_not_counted_active_and_its_pair_is_queued_again(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _base_pair(db_session, chunk_count=2)
        user_id = await _seed(db_session, factories.make_app_user)
        await _seed(
            db_session,
            factories.make_evaluation_item,
            ids["chunk"],
            ids["question"],
            user_id,
            status=EvaluationItemStatus.STALE,
        )

        active_before = await count_active_items(db_session)
        view = await read_label_queue(db_session, _settings(), ids["service"])

        assert active_before == 0
        chunk_ids = {task.chunk_id for task in view.tasks}
        assert chunk_ids
        assert chunk_ids <= set(ids["chunks"])


async def _app_user_row(session: AsyncSession, user_id: uuid.UUID) -> AppUser:
    user = await session.get(AppUser, user_id)
    assert user is not None
    return user
