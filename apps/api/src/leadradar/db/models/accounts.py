"""[Accounts](/architecture/sql-store.md#accounts): `account`, `account_alias`,
`account_source`, `contact`, `discovery_candidate`."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from leadradar.core.enums import (
    AccountOperationalComplexity,
    AccountOrigin,
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AccountStatus,
    ContactPersona,
    ContactPersonaOrigin,
    DiscoveryCandidateOrigin,
    DiscoveryCandidateStatus,
)
from leadradar.db.base import TimestampedBase
from leadradar.db.types import fk_uuid, pg_enum


class Account(TimestampedBase):
    """[`account`](/architecture/sql-store.md#account)."""

    __tablename__ = "account"

    domain: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    country_code: Mapped[str | None]
    industry: Mapped[str | None] = mapped_column(
        ForeignKey("industry.code", ondelete="RESTRICT"), nullable=True
    )
    employee_count: Mapped[int | None]
    revenue_eur: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operational_complexity: Mapped[AccountOperationalComplexity | None] = mapped_column(
        pg_enum(AccountOperationalComplexity, "account_operational_complexity"), nullable=True
    )
    attribute_origin: Mapped[dict[str, object]] = mapped_column(JSONB)
    parent_account_id: Mapped[uuid.UUID | None] = fk_uuid("account.id", nullable=True)
    origin: Mapped[AccountOrigin] = mapped_column(pg_enum(AccountOrigin, "account_origin"))
    status: Mapped[AccountStatus] = mapped_column(pg_enum(AccountStatus, "account_status"))
    crunchbase_id: Mapped[str | None]
    linkedin_url: Mapped[str | None]
    notes: Mapped[str | None]
    last_refreshed_at: Mapped[datetime | None]
    next_refresh_at: Mapped[datetime | None]


class AccountAlias(TimestampedBase):
    """[`account_alias`](/architecture/sql-store.md#account_alias)."""

    __tablename__ = "account_alias"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    alias: Mapped[str]
    normalised: Mapped[str]

    __table_args__ = (UniqueConstraint("account_id", "normalised"),)


class AccountSource(TimestampedBase):
    """[`account_source`](/architecture/sql-store.md#account_source)."""

    __tablename__ = "account_source"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    kind: Mapped[AccountSourceKind] = mapped_column(
        pg_enum(AccountSourceKind, "account_source_kind")
    )
    url: Mapped[str]
    origin: Mapped[AccountSourceOrigin] = mapped_column(
        pg_enum(AccountSourceOrigin, "account_source_origin")
    )
    status: Mapped[AccountSourceStatus] = mapped_column(
        pg_enum(AccountSourceStatus, "account_source_status")
    )

    __table_args__ = (UniqueConstraint("account_id", "url"),)


class Contact(TimestampedBase):
    """[`contact`](/architecture/sql-store.md#contact)."""

    __tablename__ = "contact"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    full_name: Mapped[str]
    job_title: Mapped[str]
    persona: Mapped[ContactPersona] = mapped_column(pg_enum(ContactPersona, "contact_persona"))
    persona_origin: Mapped[ContactPersonaOrigin] = mapped_column(
        pg_enum(ContactPersonaOrigin, "contact_persona_origin")
    )
    source_url: Mapped[str]
    retain_until: Mapped[date]


class DiscoveryCandidate(TimestampedBase):
    """[`discovery_candidate`](/architecture/sql-store.md#discovery_candidate)."""

    __tablename__ = "discovery_candidate"

    service_id: Mapped[uuid.UUID] = fk_uuid("service.id")
    run_id: Mapped[uuid.UUID] = fk_uuid("pipeline_run.id")
    name: Mapped[str]
    normalised_name: Mapped[str]
    domain: Mapped[str | None]
    country_code: Mapped[str | None]
    industry: Mapped[str | None] = mapped_column(
        ForeignKey("industry.code", ondelete="RESTRICT"), nullable=True
    )
    employee_count: Mapped[int | None]
    origin: Mapped[DiscoveryCandidateOrigin] = mapped_column(
        pg_enum(DiscoveryCandidateOrigin, "discovery_candidate_origin")
    )
    document_id: Mapped[uuid.UUID | None] = fk_uuid("document.id", nullable=True)
    quote: Mapped[str | None]
    fit_estimate: Mapped[int]
    status: Mapped[DiscoveryCandidateStatus] = mapped_column(
        pg_enum(DiscoveryCandidateStatus, "discovery_candidate_status")
    )
    decided_by: Mapped[uuid.UUID | None] = fk_uuid("app_user.id", nullable=True)
    decided_at: Mapped[datetime | None]
    reject_reason: Mapped[str | None]
    account_id: Mapped[uuid.UUID | None] = fk_uuid("account.id", nullable=True)

    __table_args__ = (CheckConstraint("fit_estimate BETWEEN 0 AND 100", name="fit_estimate_range"),)
