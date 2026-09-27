"""Integration tests of the worker's daily housekeeping ([Retention and erasure]
(/architecture/rules.md#retention-and-erasure)) against a real database."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Connection, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AuditAction, EvaluationItemStatus
from leadradar.db.models.accounts import Contact
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.identity import AuthSession
from leadradar.db.models.ingestion import Chunk, Document
from leadradar.db.models.outreach import OutreachDraft
from leadradar.settings import ApiSettings
from leadradar.worker.housekeeping import run_housekeeping
from tests.integration import factories as f

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 27, 3, 0, tzinfo=UTC)
PAST_DAY = date(2026, 9, 26)
FUTURE_DAY = date(2026, 9, 28)
SAME_DAY = date(2026, 9, 27)
# The store's `vector(EMBEDDING_DIM)` is frozen at migration time to this default
# (`test_migration.py`).
_EMBEDDING_DIM = ApiSettings.model_fields["embedding_dim"].default


async def _seed(session: AsyncSession, build: Callable[[Connection], Any]) -> Any:
    return await session.run_sync(lambda sync: build(sync.connection()))


async def test_a_purged_document_loses_its_text_and_its_passages_lose_theirs(
    async_session: AsyncSession,
) -> None:
    def build(conn: Connection) -> dict[str, uuid.UUID]:
        run_id = f.make_pipeline_run(conn)
        doc_id = f.make_document(conn, run_id, purge_after=PAST_DAY)
        chunk_id = f.make_chunk(conn, doc_id, embedding=[0.1] * _EMBEDDING_DIM)
        return {"doc": doc_id, "chunk": chunk_id}

    ids = await _seed(async_session, build)

    await run_housekeeping(async_session, now=NOW, session_ttl_hours=12)

    document = await async_session.get(Document, ids["doc"])
    assert document is not None
    assert document.text is None
    assert document.purged_at == NOW
    chunk = await async_session.get(Chunk, ids["chunk"])
    assert chunk is not None
    assert chunk.text is None
    assert chunk.embedding is None
    assert chunk.lexemes is None


async def test_a_passage_referenced_by_an_active_item_keeps_its_text_not_its_embedding(
    async_session: AsyncSession,
) -> None:
    def build(conn: Connection) -> dict[str, uuid.UUID]:
        user_id = f.make_app_user(conn)
        run_id = f.make_pipeline_run(conn)
        doc_id = f.make_document(conn, run_id, purge_after=PAST_DAY)
        active_chunk_id = f.make_chunk(conn, doc_id, ordinal=0, embedding=[0.1] * _EMBEDDING_DIM)
        stale_chunk_id = f.make_chunk(conn, doc_id, ordinal=1, embedding=[0.1] * _EMBEDDING_DIM)
        svc_id = f.make_service(conn)
        q_id = f.make_signal_question(conn, svc_id)
        f.make_evaluation_item(
            conn, active_chunk_id, q_id, user_id, status=EvaluationItemStatus.ACTIVE
        )
        f.make_evaluation_item(
            conn,
            stale_chunk_id,
            q_id,
            user_id,
            status=EvaluationItemStatus.STALE,
            question_revision=2,
        )
        return {"active": active_chunk_id, "stale": stale_chunk_id}

    ids = await _seed(async_session, build)

    await run_housekeeping(async_session, now=NOW, session_ttl_hours=12)

    active = await async_session.get(Chunk, ids["active"])
    assert active is not None
    assert active.text is not None
    assert active.embedding is None
    stale = await async_session.get(Chunk, ids["stale"])
    assert stale is not None
    assert stale.text is None
    assert stale.embedding is None


async def test_a_document_on_its_purge_after_day_is_untouched_and_a_second_run_changes_nothing(
    async_session: AsyncSession,
) -> None:
    def build(conn: Connection) -> uuid.UUID:
        run_id = f.make_pipeline_run(conn)
        return f.make_document(conn, run_id, purge_after=SAME_DAY)

    doc_id = await _seed(async_session, build)

    await run_housekeeping(async_session, now=NOW, session_ttl_hours=12)

    document = await async_session.get(Document, doc_id)
    assert document is not None
    assert document.text is not None
    assert document.purged_at is None

    # Idempotency: a document already past its date and purged is untouched by a second run.
    def build_past(conn: Connection) -> uuid.UUID:
        run_id = f.make_pipeline_run(conn)
        return f.make_document(conn, run_id, purge_after=PAST_DAY)

    past_doc_id = await _seed(async_session, build_past)
    await run_housekeeping(async_session, now=NOW, session_ttl_hours=12)
    first_purge = await async_session.get(Document, past_doc_id)
    assert first_purge is not None
    first_purged_at = first_purge.purged_at

    await run_housekeeping(async_session, now=NOW + timedelta(seconds=1), session_ttl_hours=12)
    document = await async_session.get(Document, past_doc_id)
    assert document is not None
    assert document.purged_at == first_purged_at


async def test_a_contact_past_retain_until_is_erased_with_one_audit_row(
    caplog: pytest.LogCaptureFixture, async_session: AsyncSession
) -> None:
    def build(conn: Connection) -> dict[str, uuid.UUID]:
        account_id = f.make_account(conn)
        service_id = f.make_service(conn)
        user_id = f.make_app_user(conn)
        contact_id = f.make_contact(
            conn, account_id, full_name="Jamie Erasable", retain_until=PAST_DAY
        )
        draft_id = f.make_outreach_draft(conn, account_id, service_id, contact_id, user_id)
        kept_id = f.make_contact(conn, account_id, retain_until=FUTURE_DAY)
        return {"account": account_id, "contact": contact_id, "draft": draft_id, "kept": kept_id}

    ids = await _seed(async_session, build)

    with caplog.at_level(logging.INFO, logger="leadradar.worker.housekeeping"):
        await run_housekeeping(async_session, now=NOW, session_ttl_hours=12)

    assert await async_session.get(Contact, ids["contact"]) is None
    assert await async_session.get(Contact, ids["kept"]) is not None
    draft = await async_session.get(OutreachDraft, ids["draft"])
    assert draft is not None
    assert draft.contact_id is None

    events = (
        (
            await async_session.execute(
                select(AuditEvent).where(AuditEvent.action == AuditAction.CONTACT_ERASED.value)
            )
        )
        .scalars()
        .all()
    )
    [event] = events
    assert event.actor_id is None
    assert event.entity_type == "contact"
    assert event.entity_id == ids["contact"]
    assert event.payload == {"account_id": str(ids["account"]), "reason": "RETENTION"}
    for record in caplog.records:
        assert "Jamie Erasable" not in record.getMessage()


async def test_sessions_older_than_the_cutoff_are_deleted_newer_ones_kept(
    async_session: AsyncSession,
) -> None:
    def build(conn: Connection) -> dict[str, uuid.UUID]:
        user_id = f.make_app_user(conn)
        expired_id = f.make_auth_session(
            conn, user_id, expires_at=NOW - timedelta(hours=12, seconds=1)
        )
        revoked_id = f.make_auth_session(
            conn,
            user_id,
            expires_at=NOW + timedelta(hours=1),
            revoked_at=NOW - timedelta(hours=13),
        )
        kept_id = f.make_auth_session(conn, user_id, expires_at=NOW - timedelta(hours=11))
        return {"expired": expired_id, "revoked": revoked_id, "kept": kept_id}

    ids = await _seed(async_session, build)

    await run_housekeeping(async_session, now=NOW, session_ttl_hours=12)

    assert await async_session.get(AuthSession, ids["expired"]) is None
    assert await async_session.get(AuthSession, ids["revoked"]) is None
    assert await async_session.get(AuthSession, ids["kept"]) is not None
