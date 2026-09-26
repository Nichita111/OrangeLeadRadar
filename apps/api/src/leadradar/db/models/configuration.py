"""[Configuration](/architecture/sql-store.md#configuration): `service`, `signal_question`,
`scoring_config`, `industry`, `market`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, CheckConstraint, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from leadradar.core.enums import (
    IndustryStatus,
    MarketStatus,
    ScoringConfigStatus,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
)
from leadradar.db.base import TimestampedBase
from leadradar.db.types import fk_uuid, pg_enum


class Service(TimestampedBase):
    """[`service`](/architecture/sql-store.md#service)."""

    __tablename__ = "service"

    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str]
    value_proposition: Mapped[str]
    status: Mapped[ServiceStatus] = mapped_column(pg_enum(ServiceStatus, "service_status"))


class SignalQuestion(TimestampedBase):
    """[`signal_question`](/architecture/sql-store.md#signal_question)."""

    __tablename__ = "signal_question"

    service_id: Mapped[uuid.UUID] = fk_uuid("service.id")
    key: Mapped[str]
    text: Mapped[str]
    answer_type: Mapped[SignalQuestionAnswerType] = mapped_column(
        pg_enum(SignalQuestionAnswerType, "signal_question_answer_type")
    )
    # `none_as_null=True`: a Python `None` must bind as SQL NULL, not a JSON `null` literal, or
    # `ck_signal_question_options_only_for_choice` would see a non-null column value.
    options: Mapped[dict[str, object] | list[object] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    polarity: Mapped[SignalQuestionPolarity] = mapped_column(
        pg_enum(SignalQuestionPolarity, "signal_question_polarity")
    )
    source_types: Mapped[list[str]] = mapped_column(ARRAY(Text))
    hint_terms: Mapped[list[str]] = mapped_column(ARRAY(Text))
    revision: Mapped[int]
    status: Mapped[SignalQuestionStatus] = mapped_column(
        pg_enum(SignalQuestionStatus, "signal_question_status")
    )

    __table_args__ = (
        UniqueConstraint("service_id", "key"),
        CheckConstraint(
            "(options IS NOT NULL) = (answer_type = 'CHOICE')",
            name="options_only_for_choice",
        ),
    )


class ScoringConfig(TimestampedBase):
    """[`scoring_config`](/architecture/sql-store.md#scoring_config)."""

    __tablename__ = "scoring_config"

    service_id: Mapped[uuid.UUID] = fk_uuid("service.id")
    version: Mapped[int]
    status: Mapped[ScoringConfigStatus] = mapped_column(
        pg_enum(ScoringConfigStatus, "scoring_config_status")
    )
    settings: Mapped[dict[str, object]] = mapped_column(JSONB)
    change_note: Mapped[str | None]
    activated_at: Mapped[datetime | None]
    activated_by: Mapped[uuid.UUID | None] = fk_uuid("app_user.id", nullable=True)

    __table_args__ = (
        UniqueConstraint("service_id", "version"),
        Index(
            "uq_scoring_config_draft_per_service",
            "service_id",
            unique=True,
            postgresql_where=text("status = 'DRAFT'"),
        ),
        Index(
            "uq_scoring_config_active_per_service",
            "service_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )


class Industry(TimestampedBase):
    """[`industry`](/architecture/sql-store.md#industry)."""

    __tablename__ = "industry"

    code: Mapped[str] = mapped_column(unique=True)
    label: Mapped[str] = mapped_column(unique=True)
    status: Mapped[IndustryStatus] = mapped_column(pg_enum(IndustryStatus, "industry_status"))


class Market(TimestampedBase):
    """[`market`](/architecture/sql-store.md#market)."""

    __tablename__ = "market"

    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(unique=True)
    country_codes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    status: Mapped[MarketStatus] = mapped_column(pg_enum(MarketStatus, "market_status"))
