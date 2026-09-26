"""Integration tests for reclassification after a question change (`S-SIG-07`), with the AI
ports faked as in ``test_signal_step``."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    ClassificationStatus,
    DocumentTriageOutcome,
    FindingStatus,
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunTrigger,
)
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.db.models.signals import Classification, DocumentTriage, Finding
from leadradar.signal.reclassify import queue_reclassify
from leadradar.worker.ai.llm import EvidenceOutput
from leadradar.worker.steps import signal
from leadradar.worker.steps.signal import run_signal_job
from tests.integration import factories
from tests.integration.signal.test_signal_step import PASSAGE, QUOTE, _fake_classifier, _seed

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _fake_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(signal, "classify", _fake_classifier(about_p=0.9, p_positive=0.9))

    async def fake_evidence(*_: Any, **__: Any) -> EvidenceOutput:
        return EvidenceOutput(quote=QUOTE, rationale="Announces a cost-reduction programme.")

    monkeypatch.setattr(signal, "extract_evidence", fake_evidence)


async def _queue(session: AsyncSession, question_id: uuid.UUID) -> uuid.UUID:
    actor_id = await _seed(session, factories.make_app_user)
    return await queue_reclassify(
        session, question_id=question_id, actor_id=actor_id, request_id=None
    )


async def _jobs(session: AsyncSession, run_id: uuid.UUID, step: JobStep) -> list[Job]:
    stmt = select(Job).where(Job.run_id == run_id, Job.step == step)
    return list((await session.execute(stmt)).scalars())


async def _run(session: AsyncSession, job: Job) -> None:
    run = await session.get(PipelineRun, job.run_id)
    assert run is not None
    await run_signal_job(session, job=job, run=run, worker_instance_id="w", alert_max_age_days=14)
    await session.flush()


async def test_question_change_queues_a_reclassify_run_with_one_signal_job_per_account(
    async_session: AsyncSession,
) -> None:
    account_id = await _seed(async_session, factories.make_account)
    svc_id = await _seed(async_session, factories.make_service)
    q_id = await _seed(async_session, factories.make_signal_question, svc_id)

    run_id = await _queue(async_session, q_id)

    run = await async_session.get(PipelineRun, run_id)
    assert run is not None
    assert (run.kind, run.trigger) == (
        PipelineRunKind.RECLASSIFY,
        PipelineRunTrigger.QUESTION_CHANGE,
    )
    assert (run.service_id, run.question_id) == (svc_id, q_id)
    [job] = await _jobs(async_session, run_id, JobStep.SIGNAL)
    assert job.payload == {"account_id": str(account_id), "question_id": str(q_id)}
    assert job.priority == 3


async def test_reclassify_supersedes_classifies_this_question_only_and_queues_score(
    async_session: AsyncSession,
) -> None:
    account_id = await _seed(async_session, factories.make_account, name="Lufthansa Group")
    refresh_id = await _seed(async_session, factories.make_pipeline_run, account_id=account_id)
    doc_id = await _seed(
        async_session, factories.make_document, refresh_id, account_id=account_id, text=PASSAGE
    )
    chunk_id = await _seed(async_session, factories.make_chunk, doc_id, text=PASSAGE)
    # Stored triage never answered this service's RELEVANT question
    await _seed(
        async_session,
        factories.make_document_triage,
        doc_id,
        service_relevance={},
        outcome=DocumentTriageOutcome.IRRELEVANT,
    )
    svc_id = await _seed(async_session, factories.make_service)
    other_q = await _seed(async_session, factories.make_signal_question, svc_id)
    q_id = await _seed(async_session, factories.make_signal_question, svc_id, revision=2)
    await _seed(async_session, factories.make_classification, chunk_id, other_q, refresh_id)
    old_clf = await _seed(async_session, factories.make_classification, chunk_id, q_id, refresh_id)
    old_finding = await _seed(
        async_session, factories.make_finding, account_id, q_id, old_clf, chunk_id
    )

    run_id = await _queue(async_session, q_id)
    [job] = await _jobs(async_session, run_id, JobStep.SIGNAL)
    await _run(async_session, job)

    triage = (
        await async_session.execute(select(DocumentTriage).filter_by(document_id=doc_id))
    ).scalar_one()
    await async_session.refresh(triage)
    assert triage.outcome == DocumentTriageOutcome.KEPT
    assert str(svc_id) in triage.service_relevance

    finding = await async_session.get(Finding, old_finding)
    assert finding is not None
    await async_session.refresh(finding)
    assert finding.status == FindingStatus.SUPERSEDED

    new_clf = (
        await async_session.execute(
            select(Classification).filter_by(question_id=q_id, question_revision=2)
        )
    ).scalar_one()
    assert new_clf.status == ClassificationStatus.POSITIVE
    assert new_clf.run_id == run_id
    other_count = await async_session.execute(
        select(func.count()).select_from(Classification).filter_by(question_id=other_q)
    )
    assert other_count.scalar_one() == 1

    assert len(await _jobs(async_session, run_id, JobStep.SCORE)) == 1


async def test_only_the_last_signal_job_queues_score(async_session: AsyncSession) -> None:
    await _seed(async_session, factories.make_account)
    await _seed(async_session, factories.make_account)
    svc_id = await _seed(async_session, factories.make_service)
    q_id = await _seed(async_session, factories.make_signal_question, svc_id)
    run_id = await _queue(async_session, q_id)
    first, second = await _jobs(async_session, run_id, JobStep.SIGNAL)

    await _run(async_session, first)
    assert await _jobs(async_session, run_id, JobStep.SCORE) == []

    await async_session.execute(update(Job).where(Job.id == first.id).values(status=JobStatus.DONE))
    await _run(async_session, second)
    assert len(await _jobs(async_session, run_id, JobStep.SCORE)) == 1
