"""The worker's daily housekeeping ([Retention and erasure]
(/architecture/rules.md#retention-and-erasure); [Scheduler and housekeeping]
(/architecture/services/worker.md#scheduler-and-housekeeping)): set-based and idempotent, so a
second run the same day, or a document, contact or session already past its date, changes
nothing further."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.erasure import erase_contact
from leadradar.core.enums import EvaluationItemStatus
from leadradar.core.retention import session_deletion_cutoff, today_utc
from leadradar.db.models.accounts import Contact
from leadradar.db.models.feedback import EvaluationItem
from leadradar.db.models.identity import AuthSession
from leadradar.db.models.ingestion import Chunk, Document

logger = logging.getLogger(__name__)


async def run_housekeeping(session: AsyncSession, *, now: datetime, session_ttl_hours: int) -> None:
    """Applies every clause of [Retention and erasure] in the caller's transaction: (a) a
    document past `purge_after`, not yet purged, loses its `text`; (b) every passage of a
    document past `purge_after` loses its `embedding`, and its `text` unless an `ACTIVE`
    [`evaluation_item`](/architecture/sql-store.md#evaluation_item) references it (`lexemes`
    follows `text`, a generated column); (c) a contact past `retain_until` is erased with reason
    `RETENTION`; (d) a session expired or revoked past `SESSION_TTL_HOURS` ago is deleted. Logs
    counts only, never a name."""
    today = today_utc(now)
    past_purge_documents = select(Document.id).where(Document.purge_after < today)

    purged_documents = await session.execute(
        update(Document)
        .where(Document.purge_after < today, Document.purged_at.is_(None))
        .values(text=None, purged_at=now)
        .returning(Document.id)
    )
    documents_purged = len(purged_documents.all())

    purged_embeddings = await session.execute(
        update(Chunk)
        .where(Chunk.document_id.in_(past_purge_documents), Chunk.embedding.isnot(None))
        .values(embedding=None)
        .returning(Chunk.id)
    )
    embeddings_purged = len(purged_embeddings.all())

    referenced_by_active_item = exists(
        select(EvaluationItem.id).where(
            EvaluationItem.chunk_id == Chunk.id,
            EvaluationItem.status == EvaluationItemStatus.ACTIVE,
        )
    )
    purged_texts = await session.execute(
        update(Chunk)
        .where(
            Chunk.document_id.in_(past_purge_documents),
            Chunk.text.isnot(None),
            ~referenced_by_active_item,
        )
        .values(text=None)
        .returning(Chunk.id)
    )
    passages_purged = len(purged_texts.all())

    contact_ids = (
        (await session.execute(select(Contact.id).where(Contact.retain_until < today)))
        .scalars()
        .all()
    )
    for contact_id in contact_ids:
        await erase_contact(
            session, contact_id=contact_id, reason="RETENTION", now=now, actor_id=None
        )

    cutoff = session_deletion_cutoff(now, session_ttl_hours)
    deleted_sessions = await session.execute(
        delete(AuthSession)
        .where(or_(AuthSession.expires_at < cutoff, AuthSession.revoked_at < cutoff))
        .returning(AuthSession.id)
    )
    sessions_deleted = len(deleted_sessions.all())

    logger.info(
        "Housekeeping: %d document(s), %d embedding(s), %d passage text(s), %d contact(s), "
        "%d session(s)",
        documents_purged,
        embeddings_purged,
        passages_purged,
        len(contact_ids),
        sessions_deleted,
    )
