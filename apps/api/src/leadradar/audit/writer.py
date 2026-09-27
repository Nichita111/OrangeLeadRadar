"""Appends one row to [`audit_event`](/architecture/sql-store.md#audit_event)
([RULE-09](/requirements/business.md#business-rules), append-only). Never commits: the caller's
transaction owns the write, so the row lands with whatever else that transaction writes, or not
at all (G6 (a) of `.work/lead-signal-feedback/task.md`)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AuditEventAction, AuditEventKind
from leadradar.db.models.audit import AuditEvent


async def append_audit_event(
    session: AsyncSession,
    *,
    occurred_at: datetime,
    actor_id: uuid.UUID | None,
    kind: AuditEventKind,
    action: AuditEventAction,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    payload: dict[str, object],
    request_id: str | None,
    run_id: uuid.UUID | None = None,
) -> None:
    """Adds the row to `session` and flushes it; does not commit."""
    session.add(
        AuditEvent(
            occurred_at=occurred_at,
            actor_id=actor_id,
            kind=kind,
            action=action.value,
            entity_type=entity_type,
            entity_id=entity_id,
            run_id=run_id,
            request_id=request_id,
            payload=payload,
        )
    )
    await session.flush()
