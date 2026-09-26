"""[Feedback and evaluation](/architecture/sql-store.md#feedback-and-evaluation):
`lead_feedback`, `finding_feedback`, `evaluation_item`, `evaluation_result`."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Index, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from leadradar.core.enums import (
    DocumentTriageClassifier,
    EvaluationItemOrigin,
    EvaluationItemStatus,
    FindingFeedbackVerdict,
    FindingStrength,
    LeadFeedbackVerdict,
)
from leadradar.db.base import TimestampedBase
from leadradar.db.types import fk_uuid, pg_enum


class LeadFeedback(TimestampedBase):
    """[`lead_feedback`](/architecture/sql-store.md#lead_feedback)."""

    __tablename__ = "lead_feedback"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    service_id: Mapped[uuid.UUID] = fk_uuid("service.id")
    user_id: Mapped[uuid.UUID] = fk_uuid("app_user.id")
    score_id: Mapped[uuid.UUID] = fk_uuid("account_score.id")
    verdict: Mapped[LeadFeedbackVerdict] = mapped_column(
        pg_enum(LeadFeedbackVerdict, "lead_feedback_verdict")
    )
    note: Mapped[str | None]


class FindingFeedback(TimestampedBase):
    """[`finding_feedback`](/architecture/sql-store.md#finding_feedback)."""

    __tablename__ = "finding_feedback"

    finding_id: Mapped[uuid.UUID] = fk_uuid("finding.id")
    user_id: Mapped[uuid.UUID] = fk_uuid("app_user.id")
    verdict: Mapped[FindingFeedbackVerdict] = mapped_column(
        pg_enum(FindingFeedbackVerdict, "finding_feedback_verdict")
    )
    note: Mapped[str | None]


class EvaluationItem(TimestampedBase):
    """[`evaluation_item`](/architecture/sql-store.md#evaluation_item)."""

    __tablename__ = "evaluation_item"

    chunk_id: Mapped[uuid.UUID] = fk_uuid("chunk.id")
    question_id: Mapped[uuid.UUID] = fk_uuid("signal_question.id")
    question_revision: Mapped[int]
    expected_strength: Mapped[FindingStrength] = mapped_column(
        pg_enum(FindingStrength, "finding_strength")
    )
    origin: Mapped[EvaluationItemOrigin] = mapped_column(
        pg_enum(EvaluationItemOrigin, "evaluation_item_origin")
    )
    labelled_by: Mapped[uuid.UUID] = fk_uuid("app_user.id")
    status: Mapped[EvaluationItemStatus] = mapped_column(
        pg_enum(EvaluationItemStatus, "evaluation_item_status")
    )

    __table_args__ = (
        Index(
            "uq_evaluation_item_active",
            "chunk_id",
            "question_id",
            "question_revision",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )


class EvaluationResult(TimestampedBase):
    """[`evaluation_result`](/architecture/sql-store.md#evaluation_result)."""

    __tablename__ = "evaluation_result"

    run_id: Mapped[uuid.UUID] = fk_uuid("pipeline_run.id", unique=True)
    classifier: Mapped[DocumentTriageClassifier] = mapped_column(
        pg_enum(DocumentTriageClassifier, "document_triage_classifier")
    )
    escalation_lower: Mapped[float] = mapped_column(Numeric)
    escalation_upper: Mapped[float] = mapped_column(Numeric)
    min_precision: Mapped[float] = mapped_column(Numeric)
    min_items: Mapped[int]
    escalation_rate_target: Mapped[float] = mapped_column(Numeric)
    items: Mapped[int]
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB)
    passed: Mapped[bool]

    __table_args__ = (
        CheckConstraint("escalation_lower BETWEEN 0 AND 1", name="escalation_lower_range"),
        CheckConstraint("escalation_upper BETWEEN 0 AND 1", name="escalation_upper_range"),
        CheckConstraint("min_precision BETWEEN 0 AND 1", name="min_precision_range"),
        CheckConstraint(
            "escalation_rate_target BETWEEN 0 AND 1", name="escalation_rate_target_range"
        ),
    )
