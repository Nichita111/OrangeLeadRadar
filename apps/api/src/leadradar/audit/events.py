"""Audit event helpers for actions introduced by this task.

One function per [Audit action](/architecture/sql-store.md#audit-actions) row; each inserts
exactly one `audit_event` row. Functions are called within an open transaction; they never
commit.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AuditEventKind
from leadradar.db.models.audit import AuditEvent


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
