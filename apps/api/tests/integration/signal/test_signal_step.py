"""Integration tests for the SIGNAL step against a real PostgreSQL.

The classifier and LLM ports are replaced by fakes, so these tests exercise how the step
records triage, classifications and findings, not the AI answers themselves.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    ClassificationStatus,
    DocumentTriageOutcome,
    FindingStatus,
    JobStep,
    PipelineRunStage,
)
from leadradar.core.signal.triage import ABOUT_ACCOUNT_QUESTION_ID
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.db.models.signals import Classification, DocumentTriage, Finding
from leadradar.worker.ai.classifier import ClassifierAnswer, ClassifierRequest
from leadradar.worker.ai.gateway import BudgetExhaustedError
from leadradar.worker.ai.llm import EvidenceOutput
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import signal
from leadradar.worker.steps.signal import run_signal_job, supersede_old_revision_findings
from tests.integration import factories

pytestmark = pytest.mark.integration

PASSAGE = (
    "Lufthansa Group announced a major cost-reduction programme targeting EUR 500m"
    " in savings through process automation."
)
QUOTE = "cost-reduction programme targeting EUR 500m"


async def _seed(session: AsyncSession, make: Callable[..., uuid.UUID], *a: Any, **kw: Any) -> Any:
    return await session.run_sync(lambda s: make(s.connection(), *a, **kw))


async def _arrange(session: AsyncSession) -> dict[str, uuid.UUID]:
    account_id = await _seed(session, factories.make_account, name="Lufthansa Group")
    run_id = await _seed(session, factories.make_pipeline_run, account_id=account_id)
    doc_id = await _seed(
        session, factories.make_document, run_id, account_id=account_id, text=PASSAGE
    )
    chunk_id = await _seed(session, factories.make_chunk, doc_id, text=PASSAGE)
    svc_id = await _seed(session, factories.make_service)
    q_id = await _seed(session, factories.make_signal_question, svc_id)
    return {"run": run_id, "doc": doc_id, "chunk": chunk_id, "svc": svc_id, "q": q_id}


def _fake_classifier(*, about_p: float, p_positive: float) -> Callable[..., Any]:
    async def fake(request: ClassifierRequest, **_: Any) -> list[ClassifierAnswer]:
        answers = []
        for q in request.questions:
            if q.id == ABOUT_ACCOUNT_QUESTION_ID:
                probs = {"YES": about_p, "NO": 1 - about_p}
            elif q.kind == "SCALE":
                probs = {"WEAK": 0.0, "MEDIUM": 0.0, "STRONG": 1.0}
            elif q.id.startswith("RELEVANT_"):
                probs = {"YES": 0.9, "NO": 0.1}
            else:
                probs = {"YES": p_positive, "NO": 1 - p_positive}
            answers.append(ClassifierAnswer(question_id=q.id, probabilities=probs))
        return answers

    return fake


async def _run_job(session: AsyncSession, ids: dict[str, uuid.UUID], **payload: Any) -> None:
    run = await session.get(PipelineRun, ids["run"])
    assert run is not None
    job = Job(
        step=JobStep.SIGNAL,
        payload={"document_ids": [str(ids["doc"])], "service_ids": [str(ids["svc"])], **payload},
    )
    await run_signal_job(
        session,
        job=job,
        run=run,
        worker_instance_id="w",
        alert_max_age_days=14,
        settings=WorkerSettings(database_url=SecretStr("postgresql://unused@localhost/unused")),
    )
    await session.flush()


async def _count(session: AsyncSession, model: Any, **where: Any) -> int:
    stmt = select(func.count()).select_from(model).filter_by(**where)
    return int((await session.execute(stmt)).scalar_one())


async def test_positive_passage_yields_one_finding_and_rerun_adds_nothing(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(signal, "classify", _fake_classifier(about_p=0.9, p_positive=0.9))

    async def fake_evidence(*_: Any, **__: Any) -> EvidenceOutput:
        return EvidenceOutput(quote=QUOTE, rationale="Announces a cost-reduction programme.")

    monkeypatch.setattr(signal, "extract_evidence", fake_evidence)
    ids = await _arrange(async_session)

    await _run_job(async_session, ids)
    await _run_job(async_session, ids)

    triage = (
        await async_session.execute(select(DocumentTriage).filter_by(document_id=ids["doc"]))
    ).scalar_one()
    assert triage.outcome == DocumentTriageOutcome.KEPT
    clf = (
        await async_session.execute(select(Classification).filter_by(chunk_id=ids["chunk"]))
    ).scalar_one()
    assert clf.status == ClassificationStatus.POSITIVE
    finding = (
        await async_session.execute(select(Finding).filter_by(question_id=ids["q"]))
    ).scalar_one()
    assert finding.classification_id == clf.id
    assert finding.quote == QUOTE
    assert finding.status == FindingStatus.ACTIVE
    run = await async_session.get(PipelineRun, ids["run"])
    assert run is not None
    await async_session.refresh(run)
    assert run.stage == PipelineRunStage.EVIDENCE


async def test_document_not_about_account_is_not_classified(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(signal, "classify", _fake_classifier(about_p=0.1, p_positive=0.9))
    ids = await _arrange(async_session)

    await _run_job(async_session, ids)

    triage = (
        await async_session.execute(select(DocumentTriage).filter_by(document_id=ids["doc"]))
    ).scalar_one()
    assert triage.outcome == DocumentTriageOutcome.NOT_ABOUT_ACCOUNT
    assert await _count(async_session, Classification, chunk_id=ids["chunk"]) == 0


async def test_escalation_stopped_by_budget_stays_pending_llm(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(signal, "classify", _fake_classifier(about_p=0.9, p_positive=0.5))

    async def over_budget(*_: Any, **__: Any) -> None:
        raise BudgetExhaustedError

    monkeypatch.setattr(signal, "escalate", over_budget)
    ids = await _arrange(async_session)

    await _run_job(async_session, ids)

    clf = (
        await async_session.execute(select(Classification).filter_by(chunk_id=ids["chunk"]))
    ).scalar_one()
    assert clf.status == ClassificationStatus.PENDING_LLM
    assert await _count(async_session, Finding, question_id=ids["q"]) == 0


async def test_findings_of_an_older_revision_become_superseded(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    run = await async_session.get(PipelineRun, ids["run"])
    assert run is not None
    account_id = run.account_id
    clf_id = await _seed(
        async_session, factories.make_classification, ids["chunk"], ids["q"], ids["run"]
    )
    finding_id = await _seed(
        async_session, factories.make_finding, account_id, ids["q"], clf_id, ids["chunk"]
    )

    await supersede_old_revision_findings(async_session, question_id=ids["q"], current_revision=2)

    finding = await async_session.get(Finding, finding_id)
    assert finding is not None
    await async_session.refresh(finding)
    assert finding.status == FindingStatus.SUPERSEDED
