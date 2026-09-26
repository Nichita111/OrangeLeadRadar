"""[Outreach and CRM](/architecture/sql-store.md#outreach-and-crm): `outreach_draft`,
`crm_sync`."""

from __future__ import annotations

import uuid

from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from leadradar.core.enums import (
    CrmSyncStatus,
    CrmSyncTarget,
    OutreachDraftChannel,
    OutreachDraftStatus,
)
from leadradar.db.base import TimestampedBase
from leadradar.db.types import fk_uuid, pg_enum


class OutreachDraft(TimestampedBase):
    """[`outreach_draft`](/architecture/sql-store.md#outreach_draft)."""

    __tablename__ = "outreach_draft"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    service_id: Mapped[uuid.UUID] = fk_uuid("service.id")
    contact_id: Mapped[uuid.UUID | None] = fk_uuid("contact.id", ondelete="SET NULL", nullable=True)
    channel: Mapped[OutreachDraftChannel] = mapped_column(
        pg_enum(OutreachDraftChannel, "outreach_draft_channel")
    )
    subject: Mapped[str | None]
    body: Mapped[str]
    finding_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    edited: Mapped[bool]
    status: Mapped[OutreachDraftStatus] = mapped_column(
        pg_enum(OutreachDraftStatus, "outreach_draft_status")
    )
    created_by: Mapped[uuid.UUID] = fk_uuid("app_user.id")


class CrmSync(TimestampedBase):
    """[`crm_sync`](/architecture/sql-store.md#crm_sync)."""

    __tablename__ = "crm_sync"

    account_id: Mapped[uuid.UUID] = fk_uuid("account.id")
    service_id: Mapped[uuid.UUID] = fk_uuid("service.id")
    score_id: Mapped[uuid.UUID] = fk_uuid("account_score.id")
    target: Mapped[CrmSyncTarget] = mapped_column(pg_enum(CrmSyncTarget, "crm_sync_target"))
    external_id: Mapped[str | None]
    status: Mapped[CrmSyncStatus] = mapped_column(pg_enum(CrmSyncStatus, "crm_sync_status"))
    error: Mapped[str | None]
    requested_by: Mapped[uuid.UUID] = fk_uuid("app_user.id")
