"""[Audit](/architecture/sql-store.md#audit): `audit_event`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from leadradar.core.enums import AuditEventKind
from leadradar.db.base import TimestampedBase
from leadradar.db.types import fk_uuid, pg_enum


class AuditEvent(TimestampedBase):
    """[`audit_event`](/architecture/sql-store.md#audit_event); append-only ([RULE-09])."""

    __tablename__ = "audit_event"

    occurred_at: Mapped[datetime]
    actor_id: Mapped[uuid.UUID | None] = fk_uuid("app_user.id", nullable=True)
    kind: Mapped[AuditEventKind] = mapped_column(pg_enum(AuditEventKind, "audit_event_kind"))
    action: Mapped[str]
    entity_type: Mapped[str | None]
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    run_id: Mapped[uuid.UUID | None] = fk_uuid("pipeline_run.id", nullable=True)
    request_id: Mapped[str | None]
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_audit_event_kind_occurred_at", "kind", "occurred_at"),
        Index("ix_audit_event_run_id", "run_id"),
    )
