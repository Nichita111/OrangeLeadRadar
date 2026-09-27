"""Writes the `DETECTED` [`account_source`](/architecture/sql-store.md#account_source) rows
[Source detection](/architecture/rules.md#source-detection) (`S-ING-05`) finds. Called by
`worker.steps.detection`, once a home page's links or a `SERPAPI` search result are in hand;
this module only writes what [`leadradar.core.source_detection`]
(../core/source_detection.py) decided, in the caller's transaction."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.core.enums import (
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AuditAction,
)
from leadradar.core.source_detection import DetectedSource
from leadradar.db.models.accounts import AccountSource


async def existing_source_kinds(
    session: AsyncSession, account_id: uuid.UUID
) -> frozenset[AccountSourceKind]:
    """Every kind the account already has a source of, `MANUAL` or `DETECTED` alike ([Source
    detection](/architecture/rules.md#source-detection) Invariants: "A kind with a `MANUAL`
    source is never detected")."""
    rows = await session.execute(
        select(AccountSource.kind).where(AccountSource.account_id == account_id)
    )
    return frozenset(rows.scalars().all())


async def write_detected_sources(
    session: AsyncSession,
    account_id: uuid.UUID,
    detected: list[DetectedSource],
    *,
    run_id: uuid.UUID,
    occurred_at: datetime,
) -> list[DetectedSource]:
    """Inserts each detected source with origin `DETECTED`, skipping a URL the account already
    has ([Source detection](/architecture/rules.md#source-detection) Invariants: "An existing URL
    is never added twice") and a kind the account gained a source of since the step read its
    inputs — rereading `existing_source_kinds` in this transaction, so "a kind with a `MANUAL`
    source is never detected" holds against a concurrent `API-24` `sources` replacement. Returns
    the sources actually written, and, when any were, appends one `ACCOUNT_UPDATED`
    [`audit_event`](/architecture/sql-store.md#audit_event) naming them, with no actor and the
    refresh's `run_id` (G7)."""
    current_kinds = await existing_source_kinds(session, account_id)
    written: list[DetectedSource] = []
    for source in detected:
        if source.kind in current_kinds:
            continue
        result = await session.execute(
            pg_insert(AccountSource)
            .values(
                account_id=account_id,
                kind=source.kind,
                url=source.url,
                origin=AccountSourceOrigin.DETECTED,
                status=AccountSourceStatus.ACTIVE,
            )
            .on_conflict_do_nothing(index_elements=["account_id", "url"])
            .returning(AccountSource.id)
        )
        if result.first() is not None:
            written.append(source)
    if written:
        await append_audit_event(
            session,
            action=AuditAction.ACCOUNT_UPDATED,
            occurred_at=occurred_at,
            actor_id=None,
            entity_type="account",
            entity_id=account_id,
            payload={"sources": [{"kind": s.kind.value, "url": s.url} for s in written]},
            run_id=run_id,
        )
    return written
