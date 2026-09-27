"""Question-scoped retrieval over one stored document ([Chunking and passage selection]
(/architecture/rules.md#chunking-and-passage-selection), [ADR-16]
(/architecture/adrs/adr-16-question-scoped-hybrid-passage-selection.md)): the keyword ranking
comes from PostgreSQL's `simple` text search, the meaning ranking is computed over the
document's stored vectors, and `core.chunking` fuses and caps them.

The meaning ranking is deliberately not an `ORDER BY embedding <=> …` query: with a document
filter the HNSW index can return fewer rows than the document has passages."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.chunking import rank_by_meaning, select_for_questions
from leadradar.db.models.ingestion import Chunk


async def keyword_ranking(
    session: AsyncSession, *, document_id: uuid.UUID, hint_terms: Sequence[str], limit: int
) -> list[int]:
    """The `ordinal`s of the document's passages containing a hint term as a phrase, by
    `ts_rank`, best first, ties by `ordinal`; empty without hint terms."""
    if not hint_terms:
        return []
    parameters = {f"term{index}": term for index, term in enumerate(hint_terms)}
    query = " || ".join(f"phraseto_tsquery('simple', :{name})" for name in parameters)
    statement = text(
        f"SELECT ordinal FROM chunk, (SELECT {query} AS q) AS hint "
        "WHERE document_id = :document_id AND lexemes @@ hint.q "
        "ORDER BY ts_rank(lexemes, hint.q) DESC, ordinal LIMIT :limit"
    )
    rows = await session.execute(
        statement, {**parameters, "document_id": document_id, "limit": limit}
    )
    return [ordinal for (ordinal,) in rows]


async def select_document_passages(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    questions: Sequence[tuple[str, Sequence[str], Sequence[float]]],
    passages_per_question: int,
    candidates: int,
    rrf_k: int,
    max_passages_per_document: int,
) -> list[int]:
    """The `ordinal`s selected for the document across `questions`, each `(id, hint_terms,
    question vector)`."""
    rows = (
        await session.execute(
            select(Chunk.ordinal, Chunk.embedding).where(
                Chunk.document_id == document_id, Chunk.embedding.is_not(None)
            )
        )
    ).all()
    passages = [
        (ordinal, [float(value) for value in vector])
        for ordinal, vector in rows
        if vector is not None
    ]
    keyword = {
        question_id: await keyword_ranking(
            session, document_id=document_id, hint_terms=hint_terms, limit=candidates
        )
        for question_id, hint_terms, _ in questions
    }
    meaning = {
        question_id: rank_by_meaning(passages, vector)[:candidates]
        for question_id, _, vector in questions
    }
    return select_for_questions(
        keyword,
        meaning,
        passages_per_question=passages_per_question,
        candidates=candidates,
        rrf_k=rrf_k,
        max_passages_per_document=max_passages_per_document,
    )
