"""The `PROCESS` step ([Chunking and passage selection]
(/architecture/rules.md#chunking-and-passage-selection), [Document normalisation]
(/architecture/rules.md#document-normalisation) step 6): embeds every passage of the run's
documents, marks near duplicates by first-passage similarity, and enqueues the run's `SIGNAL`
job. Embeddings are committed batch by batch outside the step's transaction, so a retry or a
reclaimed job resumes with the passages still without one."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import ColumnElement, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.ai.embedder import embed
from leadradar.ai.errors import UpstreamUnavailable
from leadradar.core.document_normalisation import DatedVector, near_duplicate_of
from leadradar.core.enums import JobStep
from leadradar.core.job_queue import job_priority
from leadradar.db.models.ingestion import Chunk, Document, Job
from leadradar.runs.enqueue import add_job
from leadradar.worker.steps import StepContext, StepFailed
from leadradar.worker.steps.signal import has_pending_signal_work

_FIRST_PASSAGE = 0


async def _embed_passages(context: StepContext) -> None:
    sessions = context.sessions
    if sessions is None or context.embedder is None:
        raise RuntimeError("The PROCESS step requires a session factory and the embedder client")
    settings = context.settings
    while True:
        async with sessions() as session, session.begin():
            rows = (
                await session.execute(
                    select(Chunk.id, Chunk.text)
                    .join(Document, Document.id == Chunk.document_id)
                    .where(
                        Document.run_id == context.job.run_id,
                        Chunk.embedding.is_(None),
                        Chunk.text.is_not(None),
                    )
                    .order_by(Chunk.document_id, Chunk.ordinal)
                    .limit(settings.embed_batch_size)
                )
            ).all()
        if not rows:
            return
        try:
            vectors = await embed(
                context.embedder,
                embedder_url=settings.embedder_url,
                dim=settings.embedding_dim,
                batch_size=settings.embed_batch_size,
                texts=[text for _, text in rows if text is not None],
            )
        except UpstreamUnavailable as error:
            raise StepFailed("UPSTREAM_UNAVAILABLE", str(error)) from error
        async with sessions() as session, session.begin():
            for (chunk_id, _), vector in zip(rows, vectors, strict=True):
                await session.execute(
                    update(Chunk)
                    .where(Chunk.id == chunk_id, Chunk.embedding.is_(None))
                    .values(embedding=vector)
                )


async def _first_passages(
    session: AsyncSession, *conditions: ColumnElement[bool]
) -> list[DatedVector]:
    """The not-yet-duplicate documents matching `conditions`, with their embedded first
    passage."""
    rows = (
        await session.execute(
            select(
                Document.id,
                Document.published_at,
                Document.fetched_at,
                Document.content_hash,
                Chunk.embedding,
            )
            .join(Chunk, (Chunk.document_id == Document.id) & (Chunk.ordinal == _FIRST_PASSAGE))
            .where(Document.duplicate_of_id.is_(None), Chunk.embedding.is_not(None), *conditions)
        )
    ).all()
    return [
        DatedVector(
            document_id,
            published_at or fetched_at,
            content_hash,
            [float(value) for value in vector],
        )
        for document_id, published_at, fetched_at, content_hash, vector in rows
        if vector is not None
    ]


async def _mark_near_duplicates(context: StepContext) -> None:
    session = context.session
    account_id = context.job.account_id
    settings = context.settings
    run_documents = await _first_passages(session, Document.run_id == context.job.run_id)
    if not run_documents:
        return
    window = timedelta(days=settings.near_duplicate_window_days)
    dates = [vector.dated for vector in run_documents]
    dated = func.coalesce(Document.published_at, Document.fetched_at)
    candidates = {
        vector.id: vector
        for vector in await _first_passages(
            session,
            Document.account_id == account_id,
            dated >= min(dates) - window,
            dated <= max(dates) + window,
        )
    }
    for vector in sorted(run_documents, key=lambda item: (item.dated, item.content_hash)):
        original = near_duplicate_of(
            vector,
            list(candidates.values()),
            similarity=settings.near_duplicate_similarity,
            window_days=settings.near_duplicate_window_days,
        )
        if original is not None:
            await session.execute(
                update(Document).where(Document.id == vector.id).values(duplicate_of_id=original)
            )
            del candidates[vector.id]


async def _enqueue_signal(context: StepContext) -> None:
    session = context.session
    run_id = context.job.run_id
    account_id = context.job.account_id
    if account_id is None:
        raise ValueError(f"PROCESS step: run {run_id} has no account_id")
    has_work = await has_pending_signal_work(session, account_id)
    already = await session.scalar(
        select(exists().where(Job.run_id == run_id, Job.step == JobStep.SIGNAL))
    )
    if has_work and not already:
        add_job(
            session,
            run_id=run_id,
            step=JobStep.SIGNAL,
            payload={},
            priority=job_priority(context.job.run_kind, context.job.run_trigger),
            now=context.now,
        )


async def run_process_step(context: StepContext) -> None:
    """Embeds the passages of the job's run, marks its near duplicates and, when the account has a
    document to triage or a pair waiting for the LLM, enqueues its `SIGNAL` job."""
    await _embed_passages(context)
    await _mark_near_duplicates(context)
    await _enqueue_signal(context)
