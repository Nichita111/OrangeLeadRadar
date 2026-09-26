"""The one writer of [`audit_event`](/architecture/sql-store.md#audit_event)
([S-AUD-01](/requirements/system.md), [RULE-09](/requirements/business.md#business-rules)):
every capability that records who did what calls `append_audit_event`, never `INSERT`s the
table itself. There is no update or delete function; the table is append-only."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AUDIT_ACTION_KIND, AuditAction, AuditEventKind
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


async def write_scoring_activated(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    scoring_config_id: uuid.UUID,
    version: int,
    previous_version: int | None,
    change_note: str,
    request_id: str | None,
) -> None:
    """Write a `SCORING_ACTIVATED` audit row.

    Payload: `version`, `previous_version`, `change_note`
    ([Audit actions](/architecture/sql-store.md#audit-actions)).
    """
    session.add(
        AuditEvent(
            occurred_at=datetime.now(tz=UTC),
            actor_id=actor_id,
            kind=AuditEventKind.CONFIG,
            action="SCORING_ACTIVATED",
            entity_type="scoring_config",
            entity_id=scoring_config_id,
            run_id=None,
            request_id=request_id,
            payload={
                "version": version,
                "previous_version": previous_version,
                "change_note": change_note,
            },
        )
    )


async def write_run_requested(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    run_id: uuid.UUID,
    kind: str,
    trigger: str,
    request_id: str | None,
) -> None:
    """Write a `RUN_REQUESTED` audit row.

    Payload: `kind`, `trigger`
    ([Audit actions](/architecture/sql-store.md#audit-actions)).
    """
    session.add(
        AuditEvent(
            occurred_at=datetime.now(tz=UTC),
            actor_id=actor_id,
            kind=AuditEventKind.RUN,
            action="RUN_REQUESTED",
            entity_type="pipeline_run",
            entity_id=run_id,
            run_id=run_id,
            request_id=request_id,
            payload={"kind": kind, "trigger": trigger},
        )
    )


async def write_run_finished(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    status: str,
    progress: dict[str, object],
) -> None:
    """Write a `RUN_FINISHED` audit row (worker side).

    Payload: `status`, `progress`
    ([Audit actions](/architecture/sql-store.md#audit-actions)).
    """
    session.add(
        AuditEvent(
            occurred_at=datetime.now(tz=UTC),
            actor_id=None,
            kind=AuditEventKind.RUN,
            action="RUN_FINISHED",
            entity_type="pipeline_run",
            entity_id=run_id,
            run_id=run_id,
            request_id=None,
            payload={"status": status, "progress": progress},
        )
    )
