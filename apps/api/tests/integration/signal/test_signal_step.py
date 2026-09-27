"""Integration tests for the SIGNAL step against a real PostgreSQL.

The classifier and LLM ports are replaced by fakes, so these tests exercise how the step
records triage, classifications and findings, not the AI answers themselves.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from leadradar.ai.audit import AiCallContext
from leadradar.ai.errors import BudgetExhausted, UpstreamUnavailable
from leadradar.ai.fixtures import FixtureMissing
from leadradar.ai.shapes import (
    ClassifierAnswer,
    ClassifierRequest,
    EscalationInput,
    EscalationOutput,
    EvidenceInput,
    EvidenceOutput,
)
from leadradar.core.enums import (
    ClassificationStatus,
    Dependency,
    DocumentTriageOutcome,
    FindingStatus,
    JobStatus,
    JobStep,
    PipelineRunStage,
    PipelineRunStatus,
)
from leadradar.core.signal.triage import ABOUT_ACCOUNT_QUESTION_ID
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.db.models.signals import Classification, DocumentTriage, Finding
from leadradar.worker.loop import process_next_job
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import StepContext, StepFailed, StepHandler
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


async def _arrange_two_questions(session: AsyncSession) -> dict[str, uuid.UUID]:
    """As `_arrange`, but with a second question of the same service on the same passage, so one
    classify call yields two pairs for `_node_evidence` (G2's "no further LLM call")."""
    ids = await _arrange(session)
    ids["q2"] = await _seed(session, factories.make_signal_question, ids["svc"])
    return ids


def _fake_classifier(
    *, about_p: float, p_positive: float
) -> Callable[[ClassifierRequest], Awaitable[list[ClassifierAnswer]]]:
    async def fake(request: ClassifierRequest) -> list[ClassifierAnswer]:
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


class FakeGateway:
    def __init__(
        self,
        *,
        about_p: float,
        p_positive: float,
        budget_exhausted: bool = False,
        classify_raises: Exception | None = None,
        llm_raises: Exception | None = None,
    ):
        self.classifier = _fake_classifier(about_p=about_p, p_positive=p_positive)
        self.budget_exhausted = budget_exhausted
        self.classify_raises = classify_raises
        self.llm_raises = llm_raises
        self.escalate_calls = 0
        self.evidence_calls = 0

    async def classify(
        self, request: ClassifierRequest, context: AiCallContext
    ) -> list[ClassifierAnswer]:
        if self.classify_raises is not None:
            raise self.classify_raises
        return await self.classifier(request)

    async def escalate(
        self, role_input: EscalationInput, context: AiCallContext
    ) -> EscalationOutput:
        self.escalate_calls += 1
        if self.llm_raises is not None:
            raise self.llm_raises
        if self.budget_exhausted:
            raise BudgetExhausted(datetime(2026, 9, 27, tzinfo=UTC))
        raise AssertionError("Unexpected escalation")

    async def extract_evidence(
        self, role_input: EvidenceInput, context: AiCallContext
    ) -> EvidenceOutput:
        self.evidence_calls += 1
        if self.llm_raises is not None:
            raise self.llm_raises
        return EvidenceOutput(
            quote=QUOTE, quote_en=None, rationale="Announces a cost-reduction programme."
        )


async def _run_job(
    session: AsyncSession, ids: dict[str, uuid.UUID], gateway: FakeGateway, **payload: Any
) -> None:
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
        gateway=gateway,
        now=datetime(2026, 9, 26, tzinfo=UTC),
    )
    await session.flush()


async def _count(session: AsyncSession, model: Any, **where: Any) -> int:
    stmt = select(func.count()).select_from(model).filter_by(**where)
    return int((await session.execute(stmt)).scalar_one())


async def test_positive_passage_yields_one_finding_and_rerun_adds_nothing(
    async_session: AsyncSession,
) -> None:
    gateway = FakeGateway(about_p=0.9, p_positive=0.9)
    ids = await _arrange(async_session)

    await _run_job(async_session, ids, gateway)
    await _run_job(async_session, ids, gateway)

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
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)

    await _run_job(async_session, ids, FakeGateway(about_p=0.1, p_positive=0.9))

    triage = (
        await async_session.execute(select(DocumentTriage).filter_by(document_id=ids["doc"]))
    ).scalar_one()
    assert triage.outcome == DocumentTriageOutcome.NOT_ABOUT_ACCOUNT
    assert await _count(async_session, Classification, chunk_id=ids["chunk"]) == 0


async def test_escalation_stopped_by_budget_stays_pending_llm(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)

    await _run_job(
        async_session, ids, FakeGateway(about_p=0.9, p_positive=0.5, budget_exhausted=True)
    )

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


class TestClassifierUnavailable:
    """N-06 classifier: a classifier call that fails raises `StepFailed`, retried under Retries
    (DC3); no classification or finding of the batch is stored."""

    async def test_upstream_unavailable_raises_step_failed_naming_the_classifier(
        self, async_session: AsyncSession
    ) -> None:
        ids = await _arrange(async_session)
        gateway = FakeGateway(
            about_p=0.9,
            p_positive=0.9,
            classify_raises=UpstreamUnavailable(Dependency.CLASSIFIER, "ERROR", "boom"),
        )

        with pytest.raises(StepFailed) as excinfo:
            await _run_job(async_session, ids, gateway)

        assert excinfo.value.code == "UPSTREAM_UNAVAILABLE"
        assert excinfo.value.dependency == Dependency.CLASSIFIER
        assert await _count(async_session, DocumentTriage, document_id=ids["doc"]) == 0
        assert await _count(async_session, Classification, chunk_id=ids["chunk"]) == 0
        assert await _count(async_session, Finding, question_id=ids["q"]) == 0

    async def test_a_missing_recording_raises_step_failed_fixture_missing(
        self, async_session: AsyncSession
    ) -> None:
        ids = await _arrange(async_session)
        gateway = FakeGateway(
            about_p=0.9,
            p_positive=0.9,
            classify_raises=FixtureMissing("openrouter", "some-key"),
        )

        with pytest.raises(StepFailed) as excinfo:
            await _run_job(async_session, ids, gateway)

        assert excinfo.value.code == "FIXTURE_MISSING"
        assert excinfo.value.dependency is None

    async def test_after_job_max_attempts_the_run_holds_the_dependency_and_ends_partial(
        self, async_connection: AsyncConnection
    ) -> None:
        """[Job queue](/architecture/services/worker.md#job-queue) Retries, driven through the
        real job loop (`record_job_failure`, not `run_signal_job` called directly): after its
        last attempt, the run's `errors` entry names the classifier and, once the job loop
        enqueues and runs the owed `SCORE` job, the run ends `PARTIAL` (R-2)."""

        now = datetime(2026, 9, 26, tzinfo=UTC)

        def build(conn: Connection) -> uuid.UUID:
            account_id = factories.make_account(conn, name="Lufthansa Group")
            run_id = factories.make_pipeline_run(conn, account_id=account_id)
            doc_id = factories.make_document(conn, run_id, account_id=account_id, text=PASSAGE)
            factories.make_chunk(conn, doc_id, text=PASSAGE)
            svc_id = factories.make_service(conn)
            factories.make_signal_question(conn, svc_id)
            factories.make_job(
                conn,
                run_id,
                step=JobStep.SIGNAL,
                payload={"document_ids": [str(doc_id)], "service_ids": [str(svc_id)]},
                not_before=now,
            )
            return run_id

        run_id = await async_connection.run_sync(build)
        gateway = FakeGateway(
            about_p=0.9,
            p_positive=0.9,
            classify_raises=UpstreamUnavailable(Dependency.CLASSIFIER, "ERROR", "boom"),
        )

        def session_factory() -> AsyncSession:
            return AsyncSession(
                bind=async_connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )

        async def signal_handler(context: StepContext) -> None:
            job = await context.session.get(Job, context.job.id)
            run = await context.session.get(PipelineRun, context.job.run_id)
            assert job is not None and run is not None
            await run_signal_job(
                context.session,
                job=job,
                run=run,
                worker_instance_id=str(context.job.id),
                alert_max_age_days=14,
                settings=context.settings,
                gateway=gateway,
                now=context.now,
            )

        async def score_handler(context: StepContext) -> None:
            return None

        handlers: dict[JobStep, StepHandler] = {
            JobStep.SIGNAL: signal_handler,
            JobStep.SCORE: score_handler,
        }
        settings = WorkerSettings(
            database_url=SecretStr("postgresql://unused@localhost/unused"),
            job_max_attempts=1,
        )

        while await process_next_job(
            session_factory, handlers=handlers, settings=settings, clock=lambda: now, worker_id="w"
        ):
            pass

        run = (
            await async_connection.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        ).one()
        assert run.status is PipelineRunStatus.PARTIAL
        assert run.errors == [
            {
                "stage": "TRIAGE",
                "dependency": "CLASSIFIER",
                "code": "UPSTREAM_UNAVAILABLE",
                "message": "boom",
            }
        ]


class TestLlmUnavailableDuringEvidence:
    """N-06 LLM, G2: an escalation or evidence call whose LLM is unavailable leaves its pair
    `PENDING_LLM`, like a budget stop; the job then makes no further LLM call, and the run ends
    `PARTIAL` through one `errors` entry naming the LLM."""

    async def test_escalation_unavailable_leaves_the_pair_pending_with_one_run_error(
        self, async_session: AsyncSession
    ) -> None:
        ids = await _arrange(async_session)
        gateway = FakeGateway(
            about_p=0.9,
            p_positive=0.5,
            llm_raises=UpstreamUnavailable(Dependency.LLM, "ERROR", "OpenRouter is down"),
        )

        await _run_job(async_session, ids, gateway)

        clf = (
            await async_session.execute(select(Classification).filter_by(chunk_id=ids["chunk"]))
        ).scalar_one()
        assert clf.status == ClassificationStatus.PENDING_LLM
        assert await _count(async_session, Finding, question_id=ids["q"]) == 0
        run = await async_session.get(PipelineRun, ids["run"])
        assert run is not None
        await async_session.refresh(run)
        assert run.errors == [
            {
                "stage": "EVIDENCE",
                "dependency": "LLM",
                "code": "UPSTREAM_UNAVAILABLE",
                "message": "The LLM is unavailable.",
            }
        ]

    async def test_evidence_extraction_unavailable_leaves_the_pair_pending_with_one_run_error(
        self, async_session: AsyncSession
    ) -> None:
        ids = await _arrange(async_session)
        gateway = FakeGateway(
            about_p=0.9,
            p_positive=0.9,
            llm_raises=UpstreamUnavailable(Dependency.LLM, "TIMEOUT", "OpenRouter timed out"),
        )

        await _run_job(async_session, ids, gateway)

        clf = (
            await async_session.execute(select(Classification).filter_by(chunk_id=ids["chunk"]))
        ).scalar_one()
        assert clf.status == ClassificationStatus.PENDING_LLM
        assert await _count(async_session, Finding, question_id=ids["q"]) == 0
        run = await async_session.get(PipelineRun, ids["run"])
        assert run is not None
        await async_session.refresh(run)
        assert run.errors == [
            {
                "stage": "EVIDENCE",
                "dependency": "LLM",
                "code": "UPSTREAM_UNAVAILABLE",
                "message": "The LLM is unavailable.",
            }
        ]

    async def test_no_further_llm_call_once_unavailable_leaves_every_remaining_pair_pending(
        self, async_session: AsyncSession
    ) -> None:
        ids = await _arrange_two_questions(async_session)
        gateway = FakeGateway(
            about_p=0.9,
            p_positive=0.5,
            llm_raises=UpstreamUnavailable(Dependency.LLM, "ERROR", "OpenRouter is down"),
        )

        await _run_job(async_session, ids, gateway)

        classifications = (
            (await async_session.execute(select(Classification).filter_by(chunk_id=ids["chunk"])))
            .scalars()
            .all()
        )
        assert len(classifications) == 2
        assert {clf.status for clf in classifications} == {ClassificationStatus.PENDING_LLM}
        assert gateway.escalate_calls == 1
        run = await async_session.get(PipelineRun, ids["run"])
        assert run is not None
        await async_session.refresh(run)
        assert len(run.errors) == 1

    async def test_driven_through_the_job_loop_the_job_ends_done_and_the_run_partial(
        self, async_connection: AsyncConnection
    ) -> None:
        """A-8: driven through the real job loop (`complete_job`, not `run_signal_job` called
        directly). The LLM-unavailable pair is not a step failure, so the job ends `DONE`; the
        run still ends `PARTIAL`, once the owed `SCORE` job runs, through `_settle_run`'s
        `has_errors` path (G2)."""

        now = datetime(2026, 9, 26, tzinfo=UTC)

        def build(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
            account_id = factories.make_account(conn, name="Lufthansa Group")
            run_id = factories.make_pipeline_run(conn, account_id=account_id)
            doc_id = factories.make_document(conn, run_id, account_id=account_id, text=PASSAGE)
            factories.make_chunk(conn, doc_id, text=PASSAGE)
            svc_id = factories.make_service(conn)
            factories.make_signal_question(conn, svc_id)
            job_id = factories.make_job(
                conn,
                run_id,
                step=JobStep.SIGNAL,
                payload={"document_ids": [str(doc_id)], "service_ids": [str(svc_id)]},
                not_before=now,
            )
            return run_id, job_id

        run_id, job_id = await async_connection.run_sync(build)
        gateway = FakeGateway(
            about_p=0.9,
            p_positive=0.5,
            llm_raises=UpstreamUnavailable(Dependency.LLM, "ERROR", "OpenRouter is down"),
        )

        def session_factory() -> AsyncSession:
            return AsyncSession(
                bind=async_connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )

        async def signal_handler(context: StepContext) -> None:
            job = await context.session.get(Job, context.job.id)
            run = await context.session.get(PipelineRun, context.job.run_id)
            assert job is not None and run is not None
            await run_signal_job(
                context.session,
                job=job,
                run=run,
                worker_instance_id=str(context.job.id),
                alert_max_age_days=14,
                settings=context.settings,
                gateway=gateway,
                now=context.now,
            )

        async def score_handler(context: StepContext) -> None:
            return None

        handlers: dict[JobStep, StepHandler] = {
            JobStep.SIGNAL: signal_handler,
            JobStep.SCORE: score_handler,
        }
        settings = WorkerSettings(
            database_url=SecretStr("postgresql://unused@localhost/unused"),
            job_max_attempts=1,
        )

        while await process_next_job(
            session_factory, handlers=handlers, settings=settings, clock=lambda: now, worker_id="w"
        ):
            pass

        job = (await async_connection.execute(select(Job).where(Job.id == job_id))).one()
        assert job.status is JobStatus.DONE
        run = (
            await async_connection.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        ).one()
        assert run.status is PipelineRunStatus.PARTIAL
        assert run.errors == [
            {
                "stage": "EVIDENCE",
                "dependency": "LLM",
                "code": "UPSTREAM_UNAVAILABLE",
                "message": "The LLM is unavailable.",
            }
        ]
