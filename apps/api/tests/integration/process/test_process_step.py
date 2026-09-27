"""Integration tests of the `PROCESS` step ([Chunking and passage selection]
(/architecture/rules.md#chunking-and-passage-selection), [Document normalisation]
(/architecture/rules.md#document-normalisation) step 6; `S-ING-03`, `S-ING-04`, `S-PIP-04`,
`N-05`) and of the keyword ranking of the passage selection.

The embedder is an `httpx.MockTransport`; each test runs in one outer transaction rolled back at
the end, and the step's own transactions are savepoints inside it."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from leadradar.core.enums import (
    ClassificationStatus,
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
)
from leadradar.core.job_queue import job_priority
from leadradar.db.models.ingestion import Chunk, Document, Job, PipelineRun
from leadradar.db.models.signals import Classification
from leadradar.worker.loop import process_next_job
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import STEP_HANDLERS, StepContext, StepHandler
from leadradar.worker.steps.passage_selection import keyword_ranking
from tests.integration import factories as f
from tests.integration.pipeline_doubles import T0, Clock, Embedder, session_factory, vec

pytestmark = pytest.mark.integration


def settings(**overrides: Any) -> WorkerSettings:
    values: dict[str, Any] = {
        "database_url": SecretStr("postgresql://unused"),
        "embed_batch_size": 2,
        "job_max_attempts": 1,
        "job_retry_backoff_s": 1,
    }
    values.update(overrides)
    return WorkerSettings(**values)


@pytest.fixture
async def connection(async_connection: AsyncConnection) -> AsyncIterator[AsyncConnection]:
    await async_connection.execute(
        update(Job)
        .where(Job.status.in_((JobStatus.READY, JobStatus.RUNNING)))
        .values(status=JobStatus.CANCELLED)
    )
    yield async_connection


async def _succeed(context: StepContext) -> None:
    return None


async def drain(
    connection: AsyncConnection,
    embedder: Embedder,
    worker_settings: WorkerSettings,
    clock: Clock,
    *,
    rounds: int = 1,
) -> None:
    handlers: dict[JobStep, StepHandler] = {
        JobStep.PROCESS: STEP_HANDLERS[JobStep.PROCESS],
        JobStep.SIGNAL: _succeed,
        JobStep.SCORE: _succeed,
    }
    async with embedder.client() as client:
        for _ in range(rounds):
            while await process_next_job(
                session_factory(connection),
                handlers=handlers,
                settings=worker_settings,
                clock=clock,
                worker_id="worker-1",
                embedder=client,
            ):
                pass
            clock.now += timedelta(hours=1)


async def account_with_run(connection: AsyncConnection) -> tuple[uuid.UUID, uuid.UUID]:
    def build(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        account_id = f.make_account(conn, name="Acme Corp", domain=f"{uuid.uuid4().hex}.test")
        run_id = f.make_pipeline_run(conn, account_id=account_id)
        f.make_job(conn, run_id, step=JobStep.PROCESS, not_before=T0, priority=7)
        return account_id, run_id

    return await connection.run_sync(build)


async def add_document(
    connection: AsyncConnection,
    account_id: uuid.UUID,
    run_id: uuid.UUID,
    passages: list[str],
    **overrides: Any,
) -> uuid.UUID:
    def build(conn: Connection) -> uuid.UUID:
        document_id = f.make_document(conn, run_id, account_id=account_id, **overrides)
        for ordinal, text in enumerate(passages):
            f.make_chunk(conn, document_id, ordinal=ordinal, text=text)
        return document_id

    return await connection.run_sync(build)


async def embedded(connection: AsyncConnection, document_id: uuid.UUID) -> list[bool]:
    rows = await connection.execute(
        select(Chunk.embedding.is_not(None))
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.ordinal)
    )
    return [bool(flag) for (flag,) in rows]


async def duplicate_of(connection: AsyncConnection, document_id: uuid.UUID) -> uuid.UUID | None:
    return (
        await connection.execute(select(Document.duplicate_of_id).where(Document.id == document_id))
    ).scalar_one()


async def steps_of(connection: AsyncConnection, run_id: uuid.UUID) -> list[Any]:
    rows = await connection.execute(select(Job.step, Job.priority).where(Job.run_id == run_id))
    return list(rows.all())


async def test_process_embeds_every_passage_of_its_run_in_batches_and_enqueues_signal(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)

    def other_account_run(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        other_account = f.make_account(conn, name="Other", domain=f"{uuid.uuid4().hex}.test")
        return other_account, f.make_pipeline_run(
            conn, account_id=other_account, status=PipelineRunStatus.SUCCEEDED
        )

    other_account, other_run = await connection.run_sync(other_account_run)
    document = await add_document(connection, account_id, run_id, ["a", "b", "c", "d", "e"])
    other = await add_document(connection, other_account, other_run, ["z"])
    embedder = Embedder()

    await drain(connection, embedder, settings(), Clock())

    assert await embedded(connection, document) == [True] * 5
    assert await embedded(connection, other) == [False]
    assert [len(call) for call in embedder.calls] == [2, 2, 1]
    signal_jobs = [row for row in await steps_of(connection, run_id) if row[0] is JobStep.SIGNAL]
    assert signal_jobs == [
        (JobStep.SIGNAL, job_priority(PipelineRunKind.ACCOUNT_REFRESH, PipelineRunTrigger.USER))
    ]


async def test_an_earlier_documents_passages_left_without_embeddings_are_embedded_and_checked(
    connection: AsyncConnection,
) -> None:
    """A document whose own `PROCESS` failed is processed by the account's next refresh."""
    account_id, run_id = await account_with_run(connection)
    failed_run = await connection.run_sync(
        lambda c: f.make_pipeline_run(c, account_id=account_id, status=PipelineRunStatus.PARTIAL)
    )
    orphan = await add_document(
        connection, account_id, failed_run, ["Orphan text"], published_at=T0 - timedelta(days=2)
    )
    purged = await add_document(
        connection, account_id, failed_run, ["Purged text"], purged_at=T0 - timedelta(days=1)
    )
    copy = await add_document(
        connection, account_id, run_id, ["Orphan copy"], published_at=T0 - timedelta(days=1)
    )
    embedder = Embedder({"Orphan text": vec(1.0, 0.0), "Orphan copy": vec(1.0, 0.01)})

    await drain(connection, embedder, settings(), Clock())

    assert await embedded(connection, orphan) == [True]
    assert await embedded(connection, purged) == [False]
    assert await duplicate_of(connection, copy) == orphan
    assert JobStep.SIGNAL in [step for step, _ in await steps_of(connection, run_id)]


async def test_a_translation_a_day_later_is_marked_a_duplicate_of_the_article(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)
    article = await add_document(
        connection, account_id, run_id, ["English text"], published_at=T0 - timedelta(days=2)
    )
    translation = await add_document(
        connection, account_id, run_id, ["Deutscher Text"], published_at=T0 - timedelta(days=1)
    )
    embedder = Embedder({"English text": vec(1.0, 0.0), "Deutscher Text": vec(1.0, 0.01)})

    await drain(connection, embedder, settings(), Clock())

    assert await duplicate_of(connection, translation) == article
    assert await duplicate_of(connection, article) is None


async def test_a_similar_document_beyond_the_window_or_of_another_account_is_not_marked(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)
    other_account = await connection.run_sync(lambda c: f.make_account(c, name="Other"))
    other_run = await connection.run_sync(
        lambda c: f.make_pipeline_run(
            c, account_id=other_account, status=PipelineRunStatus.SUCCEEDED
        )
    )
    same = {"text": vec(1.0)}
    old = await add_document(
        connection, account_id, other_run, ["old"], published_at=T0 - timedelta(days=30)
    )
    foreign = await add_document(
        connection, other_account, other_run, ["foreign"], published_at=T0 - timedelta(days=1)
    )
    fresh = await add_document(
        connection, account_id, run_id, ["fresh"], published_at=T0 - timedelta(days=1)
    )
    embedder = Embedder({"old": same["text"], "foreign": same["text"], "fresh": same["text"]})
    await connection.execute(
        update(Chunk).where(Chunk.document_id.in_((old, foreign))).values(embedding=same["text"])
    )

    await drain(connection, embedder, settings(), Clock())

    assert await duplicate_of(connection, fresh) is None


async def test_a_document_without_publication_date_is_dated_by_its_fetch_time(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)
    article = await add_document(
        connection,
        account_id,
        run_id,
        ["English text"],
        published_at=None,
        fetched_at=T0 - timedelta(days=2),
    )
    translation = await add_document(
        connection,
        account_id,
        run_id,
        ["Deutscher Text"],
        published_at=None,
        fetched_at=T0 - timedelta(days=1),
    )
    embedder = Embedder({"English text": vec(1.0, 0.0), "Deutscher Text": vec(1.0, 0.01)})

    await drain(connection, embedder, settings(), Clock())

    assert await duplicate_of(connection, translation) == article
    assert await duplicate_of(connection, article) is None


async def test_an_embedder_failure_keeps_the_embedded_passages_and_the_retry_completes(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)
    document = await add_document(connection, account_id, run_id, ["a", "b", "c", "d"])
    embedder = Embedder()
    embedder.fail_from_call = 1
    clock = Clock()
    worker_settings = settings(job_max_attempts=3)

    await drain(connection, embedder, worker_settings, clock)
    assert await embedded(connection, document) == [True, True, False, False]

    embedder.fail_from_call = None
    await drain(connection, embedder, worker_settings, clock, rounds=2)

    assert await embedded(connection, document) == [True] * 4
    assert [s for s, _ in await steps_of(connection, run_id)].count(JobStep.SIGNAL) == 1


async def test_after_the_last_attempt_the_job_fails_and_the_loop_owes_score(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)
    document = await add_document(connection, account_id, run_id, ["a"])
    embedder = Embedder()
    embedder.fail_from_call = 0

    await drain(connection, embedder, settings(), Clock())

    assert await embedded(connection, document) == [False]
    job = (
        await connection.execute(select(Job.status).where(Job.step == JobStep.PROCESS))
    ).scalar_one()
    assert job is JobStatus.FAILED
    errors = (
        await connection.execute(select(PipelineRun.errors).where(PipelineRun.id == run_id))
    ).scalar_one()
    assert [(e["stage"], e["code"]) for e in cast(list[Any], errors)] == [
        ("PROCESS", "UPSTREAM_UNAVAILABLE")
    ]
    assert JobStep.SCORE in [s for s, _ in await steps_of(connection, run_id)]


async def test_running_process_again_embeds_nothing_and_enqueues_no_second_signal_job(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)
    await add_document(connection, account_id, run_id, ["a", "b"])
    embedder = Embedder()
    await drain(connection, embedder, settings(), Clock())
    calls = len(embedder.calls)

    async with embedder.client() as client, session_factory(connection)() as session:
        job = (await connection.execute(select(Job).where(Job.step == JobStep.PROCESS))).one()
        context = StepContext(
            job=_claimed(job, run_id, account_id),
            session=session,
            now=T0,
            settings=settings(),
            embedder=client,
            sessions=session_factory(connection),
        )
        await STEP_HANDLERS[JobStep.PROCESS](context)
        await session.flush()

    assert len(embedder.calls) == calls
    assert [s for s, _ in await steps_of(connection, run_id)].count(JobStep.SIGNAL) == 1


def _claimed(job: Any, run_id: uuid.UUID, account_id: uuid.UUID) -> Any:
    from leadradar.worker.steps import ClaimedJob

    return ClaimedJob(
        id=job.id,
        step=JobStep.PROCESS,
        payload={},
        attempts=1,
        run_id=run_id,
        run_kind=PipelineRunKind.ACCOUNT_REFRESH,
        run_trigger=PipelineRunTrigger.USER,
        account_id=account_id,
        service_id=None,
        question_id=None,
    )


async def test_a_run_of_only_duplicates_enqueues_no_signal_and_the_loop_owes_score(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)
    earlier_run = await connection.run_sync(
        lambda c: f.make_pipeline_run(c, account_id=account_id, status=PipelineRunStatus.SUCCEEDED)
    )
    original = await add_document(
        connection, account_id, earlier_run, ["same"], published_at=T0 - timedelta(days=2)
    )
    await connection.execute(
        update(Chunk).where(Chunk.document_id == original).values(embedding=vec(1.0))
    )
    await connection.run_sync(lambda c: f.make_document_triage(c, original))
    await add_document(
        connection, account_id, run_id, ["same"], published_at=T0 - timedelta(days=1)
    )
    embedder = Embedder({"same": vec(1.0)})

    await drain(connection, embedder, settings(), Clock())

    steps = [s for s, _ in await steps_of(connection, run_id)]
    assert JobStep.SIGNAL not in steps
    assert JobStep.SCORE in steps


async def test_the_keyword_ranking_orders_phrase_matches_by_rank_and_is_empty_without_terms(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)
    document = await add_document(
        connection,
        account_id,
        run_id,
        [
            "Nothing relevant here.",
            "Celonis process mining is used.",
            "Celonis process mining, Celonis again and process mining once more.",
            "The process was mining for Celonis.",
        ],
    )
    async with session_factory(connection)() as session:
        ranking = await keyword_ranking(
            session, document_id=document, hint_terms=["Celonis process mining"], limit=10
        )
        empty = await keyword_ranking(session, document_id=document, hint_terms=[], limit=10)

    assert ranking == [2, 1]
    assert empty == []


async def test_signal_is_enqueued_for_an_untriaged_document_of_an_earlier_run_and_not_once_triaged(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)
    earlier_run = await connection.run_sync(
        lambda c: f.make_pipeline_run(c, account_id=account_id, status=PipelineRunStatus.SUCCEEDED)
    )
    document = await add_document(connection, account_id, earlier_run, ["waiting"])
    await connection.execute(
        update(Chunk).where(Chunk.document_id == document).values(embedding=vec(1.0))
    )

    await drain(connection, Embedder(), settings(), Clock())
    assert JobStep.SIGNAL in [s for s, _ in await steps_of(connection, run_id)]

    # The document is now triaged: nothing is left to do.
    def settle(conn: Connection) -> uuid.UUID:
        f.make_document_triage(conn, document)
        return f.make_pipeline_run(conn, account_id=account_id)

    second_run = await connection.run_sync(settle)
    await connection.run_sync(
        lambda c: f.make_job(c, second_run, step=JobStep.PROCESS, not_before=T0, priority=7)
    )
    await drain(connection, Embedder(), settings(), Clock())
    assert JobStep.SIGNAL not in [s for s, _ in await steps_of(connection, second_run)]


async def test_signal_is_enqueued_for_a_pair_waiting_for_the_llm_and_not_for_a_retried_one(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await account_with_run(connection)

    def arrange(conn: Connection) -> None:
        earlier = f.make_pipeline_run(
            conn, account_id=account_id, status=PipelineRunStatus.SUCCEEDED
        )
        document = f.make_document(conn, earlier, account_id=account_id)
        f.make_document_triage(conn, document)
        chunk = f.make_chunk(conn, document, embedding=vec(1.0))
        question = f.make_signal_question(conn, f.make_service(conn))
        f.make_classification(
            conn, chunk, question, earlier, status=ClassificationStatus.EVIDENCE_FAILED
        )

    await connection.run_sync(arrange)

    await drain(connection, Embedder(), settings(), Clock())
    assert JobStep.SIGNAL in [s for s, _ in await steps_of(connection, run_id)]

    await connection.execute(update(Classification).values(evidence_retried=True))
    second_run = await connection.run_sync(lambda c: f.make_pipeline_run(c, account_id=account_id))
    await connection.run_sync(
        lambda c: f.make_job(c, second_run, step=JobStep.PROCESS, not_before=T0, priority=7)
    )
    await drain(connection, Embedder(), settings(), Clock())
    assert JobStep.SIGNAL not in [s for s, _ in await steps_of(connection, second_run)]
