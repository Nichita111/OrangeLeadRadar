"""Reads that shape an [`AuditEntry`](/architecture/interfaces.md#auditentry) (`API-60`) out of
the store. Plain dataclasses; the Pydantic response model lives at the api boundary
(`api/audit_and_health.py`)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AuditAction, AuditEventKind
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.identity import AppUser
from leadradar.settings import ApiSettings


@dataclass(frozen=True)
class AuditEntryView:
    """[`AuditEntry`](/architecture/interfaces.md#auditentry)."""

    id: uuid.UUID
    occurred_at: datetime
    kind: AuditEventKind
    action: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    run_id: uuid.UUID | None
    request_id: str | None
    payload: dict[str, object]
    actor_name: str | None


@dataclass(frozen=True)
class AuditFilters:
    """The query of `API-60`; `None` does not filter. `occurred_from` left `None` resolves to
    the last `AUDIT_DEFAULT_RANGE_DAYS` days, as `API-60` states."""

    kind: Sequence[AuditEventKind] | None
    action: AuditAction | None
    actor_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    run_id: uuid.UUID | None
    occurred_from: datetime | None
    occurred_to: datetime | None


def _entry_select() -> Select[Any, Any]:
    return select(AuditEvent, AppUser.display_name).outerjoin(
        AppUser, AppUser.id == AuditEvent.actor_id
    )


def _to_view(row: Sequence[Any]) -> AuditEntryView:
    event: AuditEvent = row[0]
    actor_name: str | None = row[1]
    return AuditEntryView(
        id=event.id,
        occurred_at=event.occurred_at,
        kind=event.kind,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        run_id=event.run_id,
        request_id=event.request_id,
        payload=event.payload,
        actor_name=actor_name,
    )


async def get_audit_page(
    session: AsyncSession,
    settings: ApiSettings,
    filters: AuditFilters,
    *,
    page: int,
    page_size: int,
    now: datetime,
) -> tuple[list[AuditEntryView], int]:
    """`API-60`: one page of audit rows matching `filters`, newest first, and how many match in
    all."""
    occurred_from = (
        filters.occurred_from
        if filters.occurred_from is not None
        else now - timedelta(days=settings.audit_default_range_days)
    )
    conditions = [AuditEvent.occurred_at >= occurred_from]
    if filters.occurred_to is not None:
        conditions.append(AuditEvent.occurred_at <= filters.occurred_to)
    if filters.kind:
        conditions.append(AuditEvent.kind.in_(filters.kind))
    if filters.action is not None:
        conditions.append(AuditEvent.action == filters.action.value)
    if filters.actor_id is not None:
        conditions.append(AuditEvent.actor_id == filters.actor_id)
    if filters.entity_id is not None:
        conditions.append(AuditEvent.entity_id == filters.entity_id)
    if filters.run_id is not None:
        conditions.append(AuditEvent.run_id == filters.run_id)

    total = (
        await session.execute(select(func.count()).select_from(AuditEvent).where(*conditions))
    ).scalar_one()
    rows = await session.execute(
        _entry_select()
        .where(*conditions)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return [_to_view(row) for row in rows], total
