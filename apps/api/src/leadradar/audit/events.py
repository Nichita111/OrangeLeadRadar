"""The one writer of [`audit_event`](/architecture/sql-store.md#audit_event)
([S-AUD-01](/requirements/system.md), [RULE-09](/requirements/business.md#business-rules)):
every capability that records who did what calls `append_audit_event`, never `INSERT`s the
table itself. There is no update or delete function; the table is append-only."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AUDIT_ACTION_KIND, AuditAction
from leadradar.db.models.audit import AuditEvent
from leadradar.logs import request_id_var


async def append_audit_event(
    db: AsyncSession,
    *,
    action: AuditAction,
    occurred_at: datetime,
    actor_id: uuid.UUID | None,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    payload: Mapping[str, object],
    run_id: uuid.UUID | None = None,
) -> None:
    """Appends one row in the caller's transaction: `kind` is derived from the closed
    [Audit actions](/architecture/sql-store.md#audit-actions) vocabulary, never repeated by the
    caller; `request_id` comes from the one request id bound for the request
    ([Request identity](/architecture/services/api.md#design))."""
    db.add(
        AuditEvent(
            occurred_at=occurred_at,
            actor_id=actor_id,
            kind=AUDIT_ACTION_KIND[action],
            action=action.value,
            entity_type=entity_type,
            entity_id=entity_id,
            run_id=run_id,
            request_id=request_id_var.get(),
            payload=dict(payload),
        )
    )
