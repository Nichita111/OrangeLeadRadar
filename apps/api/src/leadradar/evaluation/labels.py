"""The label queue and manual labelling (`S-EVL-03`, `API-50` to `API-52`): the store access of
the **Label queue** paragraph of [Evaluation metrics](/architecture/rules.md#evaluation-metrics),
then `core.evaluation.label_queue`'s pure allocation; and `API-51`'s write, in one transaction
with its `ITEM_LABELLED` audit row."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Numeric, Select, Text, and_, any_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from leadradar.audit.events import append_audit_event
from leadradar.configuration.queries import question_options
from leadradar.core.enums import (
    AccountStatus,
    AuditAction,
    DocumentTriageOutcome,
    EvaluationItemOrigin,
    EvaluationItemStatus,
    FindingStrength,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
)
from leadradar.core.evaluation import Stratum, label_queue
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import Service, SignalQuestion
from leadradar.db.models.feedback import EvaluationItem
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Chunk, Document
from leadradar.db.models.signals import Classification, DocumentTriage
from leadradar.evaluation.errors import (
    ChunkNotFound,
    QuestionNotFound,
    RevisionNotCurrent,
    ServiceNotFound,
)
from leadradar.settings import ApiSettings

# --- Shapes --------------------------------------------------------------------------------


@dataclass(frozen=True)
class LabelTaskAccount:
    """`LabelTask.account`: `{id, name}`."""

    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class LabelTaskDocument:
    """`LabelTask.document`: `{title, url, language, published_at}`."""

    title: str | None
    url: str
    language: str
    published_at: datetime | None


@dataclass(frozen=True)
class LabelTaskQuestion:
    """`LabelTask.question`: `{id, key, text, answer_type, options, polarity}`."""

    id: uuid.UUID
    key: str
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[dict[str, object]] | None
    polarity: SignalQuestionPolarity


@dataclass(frozen=True)
class LabelTask:
    """[`LabelTask`](/architecture/interfaces.md#labeltask). Never carries the classifier's
    answer ("A task never shows the classifier's answer, so that labels are not biased by it")."""

    chunk_id: uuid.UUID
    passage_text: str
    question: LabelTaskQuestion
    question_revision: int
    account: LabelTaskAccount
    document: LabelTaskDocument


@dataclass(frozen=True)
class LabelQueueView:
    """[`LabelQueue`](/architecture/interfaces.md#labelqueue), the response of `API-50`."""

    tasks: list[LabelTask]
    active_items: int
    min_items: int


@dataclass(frozen=True)
class EvaluationItemView:
    """[`EvaluationItem`](/architecture/interfaces.md#evaluationitem)."""

    id: uuid.UUID
    chunk_id: uuid.UUID
    question_id: uuid.UUID
    question_revision: int
    created_at: datetime
    question_key: str
    expected_strength: FindingStrength
    origin: EvaluationItemOrigin
    status: EvaluationItemStatus
    labelled_by_name: str


@dataclass(frozen=True)
class EvaluationItemFilters:
    """The query of `API-52`; `None` does not filter."""

    question_id: uuid.UUID | None
    origin: EvaluationItemOrigin | None
    status: EvaluationItemStatus | None


# --- Label queue (`API-50`) ------------------------------------------------------------------


def _to_label_task(row: Sequence[Any]) -> LabelTask:
    chunk, question, account, document = row
    assert isinstance(chunk, Chunk)
    assert isinstance(question, SignalQuestion)
    assert isinstance(account, Account)
    assert isinstance(document, Document)
    assert chunk.text is not None  # `_base_select` excludes purged passages
    return LabelTask(
        chunk_id=chunk.id,
        passage_text=chunk.text,
        question=LabelTaskQuestion(
            id=question.id,
            key=question.key,
            text=question.text,
            answer_type=question.answer_type,
            options=question_options(question.options),
            polarity=question.polarity,
        ),
        question_revision=question.revision,
        account=LabelTaskAccount(id=account.id, name=account.name),
        document=LabelTaskDocument(
            title=document.title,
            url=document.url,
            language=document.language,
            published_at=document.published_at,
        ),
    )


def _hash_order(
    chunk_id_column: InstrumentedAttribute[uuid.UUID],
    question_id_column: InstrumentedAttribute[uuid.UUID],
) -> ColumnElement[str]:
    """The SHA-256, hex-encoded, of the text `<chunk_id>:<question_id>` (D4), for a stable order
    within a stratum ([Evaluation metrics](/architecture/rules.md#evaluation-metrics))."""
    key_text = func.concat(cast(chunk_id_column, Text), ":", cast(question_id_column, Text))
    return func.encode(func.sha256(func.convert_to(key_text, "UTF8")), "hex")


def _base_select(
    service_id: uuid.UUID, triage_relevance_min_p: float
) -> Select[Chunk, SignalQuestion, Account, Document]:
    """Candidate pairs of the **Label queue** paragraph: a passage of a kept document of an
    active account, and an applicable active question of `service_id`, without an active item.
    Not yet split into strata or ordered."""
    service_relevance = cast(DocumentTriage.service_relevance[str(service_id)].astext, Numeric)
    no_active_item = ~(
        select(EvaluationItem.id)
        .where(
            EvaluationItem.chunk_id == Chunk.id,
            EvaluationItem.question_id == SignalQuestion.id,
            EvaluationItem.status == EvaluationItemStatus.ACTIVE,
        )
        .exists()
    )
    source_type_applies = cast(Document.source_type, Text) == any_(SignalQuestion.source_types)
    return (
        select(Chunk, SignalQuestion, Account, Document)
        .select_from(Chunk)
        .join(Document, Document.id == Chunk.document_id)
        .join(DocumentTriage, DocumentTriage.document_id == Document.id)
        .join(Account, Account.id == Document.account_id)
        .join(
            SignalQuestion,
            and_(
                SignalQuestion.service_id == service_id,
                SignalQuestion.status == SignalQuestionStatus.ACTIVE,
            ),
        )
        .where(
            Chunk.text.isnot(None),
            Document.duplicate_of_id.is_(None),
            DocumentTriage.outcome == DocumentTriageOutcome.KEPT,
            service_relevance >= triage_relevance_min_p,
            Account.status == AccountStatus.ACTIVE,
            source_type_applies,
            no_active_item,
        )
    )


async def read_label_queue(
    session: AsyncSession, settings: ApiSettings, service_id: uuid.UUID
) -> LabelQueueView:
    """`API-50`. Raises `ServiceNotFound`."""
    service = await session.get(Service, service_id)
    if service is None:
        raise ServiceNotFound(f"No service {service_id}.")

    size = settings.label_queue_size
    base = _base_select(service_id, settings.triage_relevance_min_p)
    order = _hash_order(Chunk.id, SignalQuestion.id)

    classified_join = and_(
        Classification.chunk_id == Chunk.id,
        Classification.question_id == SignalQuestion.id,
        Classification.question_revision == SignalQuestion.revision,
    )

    selected = base.join(Classification, classified_join)
    low_rows = await session.execute(
        selected.where(Classification.p_positive <= settings.escalation_lower)
        .order_by(order)
        .limit(size)
    )
    high_rows = await session.execute(
        selected.where(Classification.p_positive >= settings.escalation_upper)
        .order_by(order)
        .limit(size)
    )
    band_rows = await session.execute(
        selected.where(
            Classification.p_positive > settings.escalation_lower,
            Classification.p_positive < settings.escalation_upper,
        )
        .order_by(order)
        .limit(size)
    )

    passage_count = (
        select(func.count(Chunk.id))
        .where(Chunk.document_id == Document.id)
        .correlate(Document)
        .scalar_subquery()
    )
    not_selected = base.outerjoin(Classification, classified_join).where(
        Classification.id.is_(None), passage_count > 1
    )
    not_selected_rows = await session.execute(not_selected.order_by(order).limit(size))

    strata = {
        Stratum.LOW: [_to_label_task(row) for row in low_rows.all()],
        Stratum.BAND: [_to_label_task(row) for row in band_rows.all()],
        Stratum.HIGH: [_to_label_task(row) for row in high_rows.all()],
        Stratum.NOT_SELECTED: [_to_label_task(row) for row in not_selected_rows.all()],
    }
    tasks = label_queue(strata, size)
    active = await count_active_items(session)
    return LabelQueueView(tasks=tasks, active_items=active, min_items=settings.eval_min_items)


async def count_active_items(session: AsyncSession) -> int:
    """`ACTIVE` items of `ACTIVE` questions: what a quality check would evaluate."""
    total = (
        await session.execute(
            select(func.count(EvaluationItem.id))
            .select_from(EvaluationItem)
            .join(SignalQuestion, SignalQuestion.id == EvaluationItem.question_id)
            .where(
                EvaluationItem.status == EvaluationItemStatus.ACTIVE,
                SignalQuestion.status == SignalQuestionStatus.ACTIVE,
            )
        )
    ).scalar_one()
    return total


# --- Manual labelling (`API-51`) --------------------------------------------------------------


async def _evaluation_item_view(
    session: AsyncSession, item: EvaluationItem, *, question_key: str
) -> EvaluationItemView:
    labeller = await session.get(AppUser, item.labelled_by)
    assert labeller is not None, "an evaluation item's labeller always exists"
    return EvaluationItemView(
        id=item.id,
        chunk_id=item.chunk_id,
        question_id=item.question_id,
        question_revision=item.question_revision,
        created_at=item.created_at,
        question_key=question_key,
        expected_strength=item.expected_strength,
        origin=item.origin,
        status=item.status,
        labelled_by_name=labeller.display_name,
    )


async def label_pair(
    session: AsyncSession,
    *,
    principal: AppUser,
    chunk_id: uuid.UUID,
    question_id: uuid.UUID,
    question_revision: int,
    expected_strength: FindingStrength,
    now: datetime,
) -> EvaluationItemView:
    """`API-51`: updates the pair's `ACTIVE` item in place, whatever its origin, or writes one
    when none exists (D9), with a `ITEM_LABELLED` audit row, all in one transaction. Raises
    `ChunkNotFound`, `QuestionNotFound` or `RevisionNotCurrent`."""
    try:
        chunk = await session.get(Chunk, chunk_id)
        if chunk is None:
            raise ChunkNotFound(f"No chunk {chunk_id}.")
        question = await session.get(SignalQuestion, question_id)
        if question is None:
            raise QuestionNotFound(f"No question {question_id}.")
        if question.revision != question_revision:
            raise RevisionNotCurrent(
                f"Question {question_id} is at revision {question.revision}, not"
                f" {question_revision}."
            )

        existing = (
            (
                await session.execute(
                    select(EvaluationItem)
                    .where(
                        EvaluationItem.chunk_id == chunk_id,
                        EvaluationItem.question_id == question_id,
                        EvaluationItem.status == EvaluationItemStatus.ACTIVE,
                    )
                    .order_by(EvaluationItem.question_revision.desc())
                    .limit(1)
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )

        if existing is not None:
            existing.question_revision = question_revision
            existing.expected_strength = expected_strength
            existing.origin = EvaluationItemOrigin.MANUAL
            existing.labelled_by = principal.id
            item = existing
        else:
            item = EvaluationItem(
                chunk_id=chunk_id,
                question_id=question_id,
                question_revision=question_revision,
                expected_strength=expected_strength,
                origin=EvaluationItemOrigin.MANUAL,
                labelled_by=principal.id,
                status=EvaluationItemStatus.ACTIVE,
            )
            session.add(item)
        await session.flush()

        await append_audit_event(
            session,
            occurred_at=now,
            actor_id=principal.id,
            action=AuditAction.ITEM_LABELLED,
            entity_type="evaluation_item",
            entity_id=item.id,
            payload={"expected_strength": expected_strength.value},
        )
        view = await _evaluation_item_view(session, item, question_key=question.key)
    except BaseException:
        await session.rollback()
        raise
    await session.commit()
    return view


# --- Listing (`API-52`) -----------------------------------------------------------------------


def _item_view_select() -> Select[EvaluationItem, str, str]:
    return (
        select(EvaluationItem, SignalQuestion.key, AppUser.display_name)
        .join(SignalQuestion, SignalQuestion.id == EvaluationItem.question_id)
        .join(AppUser, AppUser.id == EvaluationItem.labelled_by)
    )


def _row_to_item_view(row: Sequence[Any]) -> EvaluationItemView:
    item, question_key, labelled_by_name = row
    return EvaluationItemView(
        id=item.id,
        chunk_id=item.chunk_id,
        question_id=item.question_id,
        question_revision=item.question_revision,
        created_at=item.created_at,
        question_key=question_key,
        expected_strength=item.expected_strength,
        origin=item.origin,
        status=item.status,
        labelled_by_name=labelled_by_name,
    )


async def list_items(
    session: AsyncSession, filters: EvaluationItemFilters, *, page: int, page_size: int
) -> tuple[list[EvaluationItemView], int]:
    """`API-52`: one page of `evaluation_item` matching `filters`, newest first."""
    conditions = [
        column == value
        for column, value in (
            (EvaluationItem.question_id, filters.question_id),
            (EvaluationItem.origin, filters.origin),
            (EvaluationItem.status, filters.status),
        )
        if value is not None
    ]
    total = (
        await session.execute(select(func.count()).select_from(EvaluationItem).where(*conditions))
    ).scalar_one()
    rows = await session.execute(
        _item_view_select()
        .where(*conditions)
        .order_by(EvaluationItem.created_at.desc(), EvaluationItem.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return [_row_to_item_view(row) for row in rows], total
