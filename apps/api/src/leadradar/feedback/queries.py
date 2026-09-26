"""Reads that shape [`LeadFeedback`](/architecture/interfaces.md#leadfeedback) and
[`FindingView`](/architecture/interfaces.md#findingview) (`API-46`, `API-47`) out of the store.
Plain dataclasses, not Pydantic models: those live at the api boundary
(`api/feedback_and_alerts.py`), which shapes its response from these."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    DocumentSourceType,
    FindingDecidedBy,
    FindingFeedbackVerdict,
    FindingStatus,
    FindingStrength,
    LeadFeedbackVerdict,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SourcePluginCode,
)
from leadradar.core.score_breakdown import counted_points
from leadradar.db.models.configuration import SignalQuestion
from leadradar.db.models.ingestion import Chunk, Document
from leadradar.db.models.signals import AccountScore, Finding


@dataclass(frozen=True)
class LeadFeedbackResult:
    """[`LeadFeedback`](/architecture/interfaces.md#leadfeedback), the response of `API-46`."""

    id: uuid.UUID
    verdict: LeadFeedbackVerdict
    note: str | None
    created_at: datetime
    user_name: str


@dataclass(frozen=True)
class QuestionSummary:
    """`FindingView.question`."""

    id: uuid.UUID
    key: str
    text: str
    polarity: SignalQuestionPolarity


@dataclass(frozen=True)
class OptionSummary:
    """`FindingView.option`; `CHOICE` questions only."""

    key: str
    label: str


@dataclass(frozen=True)
class DocumentSummary:
    """`FindingView.document`."""

    id: uuid.UUID
    title: str | None
    url: str
    source_type: DocumentSourceType
    plugin_code: SourcePluginCode
    language: str
    published_at: datetime | None


@dataclass(frozen=True)
class FeedbackSummary:
    """`FindingView.feedback`: the in-force
    [`finding_feedback`](/architecture/sql-store.md#finding_feedback)."""

    verdict: FindingFeedbackVerdict
    user_name: str
    created_at: datetime


@dataclass(frozen=True)
class FindingViewData:
    """[`FindingView`](/architecture/interfaces.md#findingview), the response of `API-47`."""

    id: uuid.UUID
    account_id: uuid.UUID
    service_id: uuid.UUID
    question: QuestionSummary
    question_revision: int
    confidence: float
    quote: str
    quote_en: str | None
    rationale: str
    observed_at: datetime
    strength: FindingStrength
    decided_by: FindingDecidedBy
    status: FindingStatus
    option: OptionSummary | None
    document: DocumentSummary
    points: float | None
    feedback: FeedbackSummary | None


def _option_summary(question: SignalQuestion, option_key: str | None) -> OptionSummary | None:
    if option_key is None or question.answer_type != SignalQuestionAnswerType.CHOICE:
        return None
    options = question.options if isinstance(question.options, list) else []
    for option in options:
        if isinstance(option, dict) and option.get("key") == option_key:
            return OptionSummary(key=option_key, label=str(option.get("label")))
    return None


async def _document_summary(session: AsyncSession, chunk_id: uuid.UUID) -> DocumentSummary:
    document = (
        await session.execute(
            select(Document)
            .join(Chunk, Chunk.document_id == Document.id)
            .where(Chunk.id == chunk_id)
        )
    ).scalar_one()
    return DocumentSummary(
        id=document.id,
        title=document.title,
        url=document.url,
        source_type=document.source_type,
        plugin_code=document.plugin_code,
        language=document.language,
        published_at=document.published_at,
    )


async def _current_breakdown(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID
) -> dict[str, object] | None:
    return (
        await session.execute(
            select(AccountScore.breakdown).where(
                AccountScore.account_id == account_id,
                AccountScore.service_id == service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()


async def read_finding_view(
    session: AsyncSession,
    *,
    finding: Finding,
    question: SignalQuestion,
    feedback: FeedbackSummary,
) -> FindingViewData:
    """Assembles [`FindingView`](/architecture/interfaces.md#findingview) for one finding, given
    the finding, its question, and the feedback row to show — the one `give_finding_feedback`
    just wrote, which is in force by definition."""
    document = await _document_summary(session, finding.chunk_id)
    breakdown = await _current_breakdown(session, finding.account_id, question.service_id)
    points = counted_points(breakdown, finding.id) if breakdown is not None else None
    return FindingViewData(
        id=finding.id,
        account_id=finding.account_id,
        service_id=question.service_id,
        question=QuestionSummary(
            id=question.id, key=question.key, text=question.text, polarity=question.polarity
        ),
        question_revision=finding.question_revision,
        confidence=finding.confidence,
        quote=finding.quote,
        quote_en=finding.quote_en,
        rationale=finding.rationale,
        observed_at=finding.observed_at,
        strength=finding.strength,
        decided_by=finding.decided_by,
        status=finding.status,
        option=_option_summary(question, finding.option_key),
        document=document,
        points=points,
        feedback=feedback,
    )


async def current_score_id(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID
) -> uuid.UUID | None:
    """The id of the account and service's current
    [`account_score`](/architecture/sql-store.md#account_score), or `None` when the account, the
    service, or a current score for the pair does not exist."""
    return (
        await session.execute(
            select(AccountScore.id).where(
                AccountScore.account_id == account_id,
                AccountScore.service_id == service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
