"""The question-scoped retrieval of [Chunking and passage selection]
(/architecture/rules.md#chunking-and-passage-selection) over an account's stored passages: a
keyword and a meaning ranking fused by reciprocal rank. The api invokes it for question preview
(`API-14`) and [Contact suggestion](/architecture/rules.md#contact-suggestion) (`API-91`); it
reads and never writes."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import ColumnElement, Select, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.ai.embedder import embed
from leadradar.ai.settings import AiGatewaySettings
from leadradar.core.chunking import fuse_rankings, passage_header, retrieval_text
from leadradar.core.enums import DocumentSourceType
from leadradar.db.models.accounts import Account
from leadradar.db.models.ingestion import Chunk, Document


@dataclass(frozen=True)
class AccountPassage:
    """A stored passage with its passage header and what the caller shows of its document."""

    chunk_id: uuid.UUID
    text: str
    header: str
    language: str
    title: str | None
    url: str
    published_at: datetime | None


async def retrieve_account_passages(
    session: AsyncSession,
    account: Account,
    *,
    text: str,
    hint_terms: Sequence[str],
    source_types: Sequence[DocumentSourceType] | None,
    settings: AiGatewaySettings,
    embedder: httpx.AsyncClient,
    limit: int,
) -> list[AccountPassage]:
    """The first `limit` of the account's passages with text, of `source_types` (every type when
    `None`), by fused score for the question `text` and its `hint_terms`. Raises the embedder's
    `UpstreamUnavailable`."""

    def base() -> Select[uuid.UUID]:
        query = (
            select(Chunk.id)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.account_id == account.id, Chunk.text.isnot(None))
        )
        if source_types is not None:
            query = query.where(Document.source_type.in_(list(source_types)))
        return query

    rankings: list[list[uuid.UUID]] = []
    terms = [term for term in hint_terms if term.strip()]
    if terms:
        simple: ColumnElement[Any] = literal_column("'simple'::regconfig")
        query: ColumnElement[Any] = func.phraseto_tsquery(simple, terms[0])
        for term in terms[1:]:
            query = query.op("||")(func.phraseto_tsquery(simple, term))
        keyword = (
            base()
            .where(Chunk.lexemes.op("@@")(query))
            .order_by(func.ts_rank(Chunk.lexemes, query).desc(), Chunk.ordinal)
            .limit(settings.retrieval_candidates)
        )
        rankings.append(list((await session.execute(keyword)).scalars()))
    [vector] = await embed(
        embedder,
        embedder_url=settings.embedder_url,
        dim=settings.embedding_dim,
        batch_size=settings.embed_batch_size,
        texts=[retrieval_text(text, hint_terms)],
    )
    meaning = (
        base()
        .where(Chunk.embedding.isnot(None))
        .order_by(Chunk.embedding.cosine_distance(vector), Chunk.ordinal)
        .limit(settings.retrieval_candidates)
    )
    rankings.append(list((await session.execute(meaning)).scalars()))

    ids = list(dict.fromkeys(chunk_id for ranking in rankings for chunk_id in ranking))
    index = {chunk_id: position for position, chunk_id in enumerate(ids)}
    fused = fuse_rankings(
        [[index[c] for c in ranking] for ranking in rankings],
        candidates=settings.retrieval_candidates,
        rrf_k=settings.retrieval_rrf_k,
    )
    chosen = [ids[position] for position, _ in fused[:limit]]
    if not chosen:
        return []
    rows = {
        chunk.id: (chunk, document)
        for chunk, document in (
            await session.execute(
                select(Chunk, Document)
                .join(Document, Document.id == Chunk.document_id)
                .where(Chunk.id.in_(chosen))
            )
        ).all()
    }
    passages: list[AccountPassage] = []
    for chunk_id in chosen:
        chunk, document = rows[chunk_id]
        assert chunk.text is not None
        passages.append(
            AccountPassage(
                chunk_id=chunk.id,
                text=chunk.text,
                header=passage_header(
                    account_name=account.name,
                    document_title=document.title,
                    section=chunk.section,
                    date=(document.published_at or document.fetched_at).strftime("%Y-%m-%d"),
                ),
                language=document.language,
                title=document.title,
                url=document.url,
                published_at=document.published_at,
            )
        )
    return passages
