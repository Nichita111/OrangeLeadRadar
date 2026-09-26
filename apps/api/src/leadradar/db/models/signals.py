"""[Signals and scores](/architecture/sql-store.md#signals-and-scores): `document_triage`,
`classification`, `finding`, `account_score`, `disqualifier_override`, `alert`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Numeric, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from leadradar.core.enums import (
    AccountScoreBand,
    AccountScoreStanding,
    AlertKind,
    ClassificationStatus,
    DisqualifierOverrideStatus,
    DocumentTriageClassifier,
    DocumentTriageOutcome,
    FindingDecidedBy,
    FindingStatus,
    FindingStrength,
)
from leadradar.db.base import TimestampedBase
from leadradar.db.types import fk_uuid, pg_enum


class DocumentTriage(TimestampedBase):
    """[`document_triage`](/architecture/sql-store.md#document_triage)."""

    __tablename__ = "document_triage"

    document_id: Mapped[uuid.UUID] = fk_uuid("document.id", unique=True)
    classifier: Mapped[DocumentTriageClassifier] = mapped_column(
        pg_enum(DocumentTriageClassifier, "document_triage_classifier")
    )
    about_account_p: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    service_relevance: Mapped[dict[str, object]] = mapped_column(JSONB)
    outcome: Mapped[DocumentTriageOutcome] = mapped_column(
        pg_enum(DocumentTriageOutcome, "document_triage_outcome")
    )

    __table_args__ = (
        CheckConstraint(
            "about_account_p IS NULL OR about_account_p BETWEEN 0 AND 1",
            name="about_account_p_range",
        ),
    )


class Classification(TimestampedBase):
    """[`classification`](/architecture/sql-store.md#classification)."""

    __tablename__ = "classification"

    chunk_id: Mapped[uuid.UUID] = fk_uuid("chunk.id")
    question_id: Mapped[uuid.UUID] = fk_uuid("signal_question.id")
    question_revision: Mapped[int]
    run_id: Mapped[uuid.UUID] = fk_uuid("pipeline_run.id")
    classifier: Mapped[DocumentTriageClassifier] = mapped_column(
        pg_enum(DocumentTriageClassifier, "document_triage_classifier")
    )
    answer: Mapped[dict[str, object]] = mapped_column(JSONB)
    p_positive: Mapped[float] = mapped_column(Numeric)
    escalated: Mapped[bool]
    strength: Mapped[FindingStrength | None] = mapped_column(
        pg_enum(FindingStrength, "finding_strength"), nullable=True
    )
    status: Mapped[ClassificationStatus] = mapped_column(
        pg_enum(ClassificationStatus, "classification_status")
    )
    evidence_retried: Mapped[bool]

    __table_args__ = (
        UniqueConstraint("chunk_id", "question_id", "question_revision"),
        CheckConstraint("p_positive BETWEEN 0 AND 1", name="p_positive_range"),
    )


class Finding(TimestampedBase):
    """[`finding`](/architecture/sql-store.md#finding)."""

    __tablename__ = "finding"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    question_id: Mapped[uuid.UUID] = fk_uuid("signal_question.id")
    question_revision: Mapped[int]
    classification_id: Mapped[uuid.UUID] = fk_uuid("classification.id", unique=True)
    chunk_id: Mapped[uuid.UUID] = fk_uuid("chunk.id")
    strength: Mapped[FindingStrength] = mapped_column(pg_enum(FindingStrength, "finding_strength"))
    confidence: Mapped[float] = mapped_column(Numeric)
    decided_by: Mapped[FindingDecidedBy] = mapped_column(
        pg_enum(FindingDecidedBy, "finding_decided_by")
    )
    option_key: Mapped[str | None]
    quote: Mapped[str]
    quote_en: Mapped[str | None]
    rationale: Mapped[str]
    observed_at: Mapped[datetime]
    status: Mapped[FindingStatus] = mapped_column(pg_enum(FindingStatus, "finding_status"))

    __table_args__ = (
        Index("ix_finding_account_status", "account_id", "status"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
    )


class AccountScore(TimestampedBase):
    """[`account_score`](/architecture/sql-store.md#account_score)."""

    __tablename__ = "account_score"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    service_id: Mapped[uuid.UUID] = fk_uuid("service.id")
    scoring_config_id: Mapped[uuid.UUID] = fk_uuid("scoring_config.id")
    run_id: Mapped[uuid.UUID] = fk_uuid("pipeline_run.id")
    as_of: Mapped[datetime]
    fit: Mapped[int]
    intent: Mapped[int]
    priority: Mapped[int]
    standing: Mapped[AccountScoreStanding] = mapped_column(
        pg_enum(AccountScoreStanding, "account_score_standing")
    )
    band: Mapped[AccountScoreBand | None] = mapped_column(
        pg_enum(AccountScoreBand, "account_score_band"), nullable=True
    )
    breakdown: Mapped[dict[str, object]] = mapped_column(JSONB)
    is_current: Mapped[bool]

    __table_args__ = (
        Index(
            "uq_account_score_current",
            "account_id",
            "service_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        Index(
            "ix_account_score_prospects",
            "service_id",
            "is_current",
            "standing",
            "priority",
        ),
        CheckConstraint("fit BETWEEN 0 AND 100", name="fit_range"),
        CheckConstraint("intent BETWEEN 0 AND 100", name="intent_range"),
        CheckConstraint("priority BETWEEN 0 AND 100", name="priority_range"),
        CheckConstraint("(band IS NULL) OR (standing = 'RANKED')", name="band_only_when_ranked"),
    )


class DisqualifierOverride(TimestampedBase):
    """[`disqualifier_override`](/architecture/sql-store.md#disqualifier_override)."""

    __tablename__ = "disqualifier_override"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    service_id: Mapped[uuid.UUID] = fk_uuid("service.id")
    rule_key: Mapped[str]
    note: Mapped[str]
    created_by: Mapped[uuid.UUID] = fk_uuid("app_user.id")
    status: Mapped[DisqualifierOverrideStatus] = mapped_column(
        pg_enum(DisqualifierOverrideStatus, "disqualifier_override_status")
    )
    revoked_by: Mapped[uuid.UUID | None] = fk_uuid("app_user.id", nullable=True)
    revoked_at: Mapped[datetime | None]

    __table_args__ = (
        Index(
            "uq_disqualifier_override_active",
            "account_id",
            "service_id",
            "rule_key",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )


class Alert(TimestampedBase):
    """[`alert`](/architecture/sql-store.md#alert)."""

    __tablename__ = "alert"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    service_id: Mapped[uuid.UUID] = fk_uuid("service.id")
    kind: Mapped[AlertKind] = mapped_column(pg_enum(AlertKind, "alert_kind"))
    finding_id: Mapped[uuid.UUID | None] = fk_uuid("finding.id", nullable=True, unique=True)
    score_id: Mapped[uuid.UUID | None] = fk_uuid("account_score.id", nullable=True, unique=True)
    acknowledged_by: Mapped[uuid.UUID | None] = fk_uuid("app_user.id", nullable=True)
    acknowledged_at: Mapped[datetime | None]
