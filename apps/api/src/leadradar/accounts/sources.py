"""Writes the `DETECTED` [`account_source`](/architecture/sql-store.md#account_source) rows
[Source detection](/architecture/rules.md#source-detection) (`S-ING-05`) finds. Called by the
`WEBSITE` and `SERPAPI` adapters' fetch handling, once a home page's links or a search result are
in hand — a later task's own step handler; this module only writes what
[`leadradar.core.source_detection`](../core/source_detection.py) decided."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AccountSourceKind, AccountSourceOrigin, AccountSourceStatus
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
    session: AsyncSession, account_id: uuid.UUID, detected: list[DetectedSource]
) -> list[DetectedSource]:
    """Inserts each detected source with origin `DETECTED`, skipping a URL the account already
    has ([Source detection](/architecture/rules.md#source-detection) Invariants: "An existing URL
    is never added twice"); returns the ones actually written."""
    written: list[DetectedSource] = []
    for source in detected:
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
    return written
