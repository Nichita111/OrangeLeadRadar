"""Integration tests for the SIGNAL step against a real PostgreSQL
([Signal graph](/architecture/services/worker.md#signal-graph); `S-SIG-01` to `S-SIG-06`,
`S-SIG-09`).

The classifier and LLM ports are replaced by a scripted fake, so these tests exercise how the
step records triage, classifications and findings, not the AI answers themselves.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
    DocumentTriageClassifier,
    DocumentTriageOutcome,
    EvaluationItemStatus,
    FindingDecidedBy,
    FindingStatus,
    FindingStrength,
    JobStep,
    PipelineRunKind,
    PipelineRunStage,
    SignalQuestionAnswerType,
    SourcePluginCode,
)
from leadradar.core.signal.triage import ABOUT_ACCOUNT_QUESTION_ID
from leadradar.db.models.configuration import SignalQuestion
from leadradar.db.models.feedback import EvaluationItem
from leadradar.db.models.ingestion import Chunk, Document, Job, PipelineRun
from leadradar.db.models.signals import Classification, DocumentTriage, Finding
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import StepFailed
from leadradar.worker.steps.signal import run_signal_job, supersede_older_revisions
from tests.integration import factories

pytestmark = pytest.mark.integration

PASSAGE = (
    "Lufthansa Group announced a major cost-reduction programme targeting EUR 500m"
    " in savings through process automation."
)
QUOTE = "cost-reduction programme targeting EUR 500m"
RATIONALE = "Announces a cost-reduction programme."
NOW = datetime(2026, 9, 26, tzinfo=UTC)
VECTOR = [1.0] + [0.0] * 1023
OPTIONS = [
    {"key": "A", "label": "Provider A", "strength": "STRONG"},
    {"key": "NONE_OF_THEM", "label": "None", "strength": "NONE"},
]


async def _seed(session: AsyncSession, make: Callable[..., uuid.UUID], *a: Any, **kw: Any) -> Any:
    return await session.run_sync(lambda s: make(s.connection(), *a, **kw))


async def _arrange(
    session: AsyncSession,
    *,
    passage: str = PASSAGE,
    question: dict[str, Any] | None = None,
    **document: Any,
) -> dict[str, uuid.UUID]:
    account_id = await _seed(session, factories.make_account, name="Lufthansa Group")
    run_id = await _seed(session, factories.make_pipeline_run, account_id=account_id)
    doc_id = await _seed(
        session, factories.make_document, run_id, account_id=account_id, text=passage, **document
    )
    chunk_id = await _seed(session, factories.make_chunk, doc_id, text=passage, embedding=VECTOR)
    svc_id = await _seed(session, factories.make_service)
    q_id = await _seed(session, factories.make_signal_question, svc_id, **(question or {}))
    return {
        "account": account_id,
        "run": run_id,
        "doc": doc_id,
        "chunk": chunk_id,
        "svc": svc_id,
        "q": q_id,
    }


class FakeGateway:
    """The classifier answers `p_positive` per question id (default `p_positive`); escalation and
    evidence answer from scripts, an exception in a script is raised. Every call is recorded."""

    def __init__(
        self,
        *,
        about_p: float = 0.9,
        p_positive: float = 0.9,
        provider: DocumentTriageClassifier = DocumentTriageClassifier.LLM,
    ) -> None:
        self.about_p = about_p
        self.p_positive = p_positive
        self.relevance_p = 0.9
        self.p_by_question: dict[str, float] = {}
        self.provider = provider
        self.classify_error: Exception | None = None
        self.escalations: list[EscalationOutput | Exception] = []
        self.evidences: list[EvidenceOutput | Exception] = []
        self.requests: list[ClassifierRequest] = []
        self.escalation_calls = 0
        self.evidence_calls = 0

    @property
    def classifier(self) -> DocumentTriageClassifier:
        return self.provider

    async def classify(
        self, request: ClassifierRequest, context: AiCallContext
    ) -> list[ClassifierAnswer]:
        self.requests.append(request)
        if self.classify_error is not None:
            raise self.classify_error
        answers = []
        for q in request.questions:
            if q.id == ABOUT_ACCOUNT_QUESTION_ID:
                probs = {"YES": self.about_p, "NO": 1 - self.about_p}
            elif q.kind == "SCALE" and q.id.endswith("__SCALE"):
                probs = {"WEAK": 0.0, "MEDIUM": 0.0, "STRONG": 1.0}
            elif q.id.startswith("RELEVANT_"):
                probs = {"YES": self.relevance_p, "NO": 1 - self.relevance_p}
            elif q.kind == "CHOICE":
                p = self.p_by_question.get(q.id, self.p_positive)
                probs = {"A": p, "NONE_OF_THEM": 1 - p}
            else:
                p = self.p_by_question.get(q.id, self.p_positive)
                probs = {"YES": p, "NO": 1 - p}
            answers.append(ClassifierAnswer(question_id=q.id, probabilities=probs))
        return answers

    async def escalate(
        self, role_input: EscalationInput, context: AiCallContext
    ) -> EscalationOutput:
        self.escalation_calls += 1
        outcome = self.escalations.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def extract_evidence(
        self, role_input: EvidenceInput, context: AiCallContext
    ) -> EvidenceOutput:
        self.evidence_calls += 1
        if not self.evidences:
            return EvidenceOutput(quote=QUOTE, quote_en=None, rationale=RATIONALE)
        outcome = self.evidences.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _evidence(quote: str = QUOTE, quote_en: str | None = None) -> EvidenceOutput:
    return EvidenceOutput(quote=quote, quote_en=quote_en, rationale=RATIONALE)


def _escalation(
    strength: FindingStrength = FindingStrength.MEDIUM,
    *,
    quote: str | None = QUOTE,
    quote_en: str | None = None,
    option_key: str | None = None,
) -> EscalationOutput:
    return EscalationOutput(
        strength=strength,
        option_key=option_key,
        confidence=0.7,
        quote=quote,
        quote_en=quote_en,
        rationale=RATIONALE,
    )


async def _run_job(
    session: AsyncSession,
    ids: dict[str, uuid.UUID],
    gateway: FakeGateway,
    embedder: httpx.AsyncClient | None = None,
    reclassify: bool = False,
) -> None:
    if reclassify:
        await session.execute(
            update(PipelineRun)
            .where(PipelineRun.id == ids["run"])
            .values(
                kind=PipelineRunKind.RECLASSIFY,
                account_id=None,
                service_id=ids["svc"],
                question_id=ids["q"],
            )
        )
    run = await session.get(PipelineRun, ids["run"])
    assert run is not None
    job_id = await _seed(
        session,
        factories.make_job,
        ids["run"],
        step=JobStep.SIGNAL,
        payload={"account_id": str(ids["account"])} if reclassify else {},
    )
    job = await session.get(Job, job_id)
    assert job is not None
    await run_signal_job(
        session,
        job=job,
        run=run,
        settings=WorkerSettings(database_url=SecretStr("postgresql://unused@localhost/unused")),
        gateway=gateway,
        embedder=embedder or httpx.AsyncClient(),
    )
    await session.flush()


def _attempts() -> int:
    settings = WorkerSettings(database_url=SecretStr("postgresql://unused@localhost/unused"))
    return settings.evidence_max_attempts


async def _count(session: AsyncSession, model: Any, **where: Any) -> int:
    stmt = select(func.count()).select_from(model).filter_by(**where)
    return int((await session.execute(stmt)).scalar_one())


async def _one(session: AsyncSession, model: Any, **where: Any) -> Any:
    row: Any = (await session.execute(select(model).filter_by(**where))).scalar_one()
    await session.refresh(row)
    return row


async def _run(session: AsyncSession, ids: dict[str, uuid.UUID]) -> PipelineRun:
    run = await session.get(PipelineRun, ids["run"])
    assert run is not None
    await session.refresh(run)
    return run


async def test_positive_passage_yields_one_finding_and_rerun_adds_nothing(
    async_session: AsyncSession,
) -> None:
    gateway = FakeGateway(provider=DocumentTriageClassifier.JEV)
    ids = await _arrange(async_session)

    await _run_job(async_session, ids, gateway)
    await _run_job(async_session, ids, gateway)

    triage = await _one(async_session, DocumentTriage, document_id=ids["doc"])
    assert triage.outcome == DocumentTriageOutcome.KEPT
    assert triage.classifier == DocumentTriageClassifier.JEV
    clf = await _one(async_session, Classification, chunk_id=ids["chunk"])
    assert clf.status == ClassificationStatus.POSITIVE
    assert clf.classifier == DocumentTriageClassifier.JEV
    finding = await _one(async_session, Finding, question_id=ids["q"])
    assert finding.classification_id == clf.id
    assert finding.quote == QUOTE
    assert finding.status == FindingStatus.ACTIVE
    assert finding.decided_by == FindingDecidedBy.CLASSIFIER
    assert (await _run(async_session, ids)).stage == PipelineRunStage.EVIDENCE


async def test_triage_state_starts_with_the_title_and_an_own_source_skips_about_account(
    async_session: AsyncSession,
) -> None:
    gateway = FakeGateway()
    ids = await _arrange(
        async_session, plugin_code=SourcePluginCode.WEBSITE, title="Hub opens in Hamburg"
    )

    await _run_job(async_session, ids, gateway)

    triage_request = gateway.requests[0]
    assert triage_request.state.startswith("Hub opens in Hamburg\n")
    assert ABOUT_ACCOUNT_QUESTION_ID not in [q.id for q in triage_request.questions]
    triage = await _one(async_session, DocumentTriage, document_id=ids["doc"])
    assert triage.about_account_p is None


async def test_document_not_about_account_is_not_classified(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)

    await _run_job(async_session, ids, FakeGateway(about_p=0.1))

    triage = await _one(async_session, DocumentTriage, document_id=ids["doc"])
    assert triage.outcome == DocumentTriageOutcome.NOT_ABOUT_ACCOUNT
    assert await _count(async_session, Classification, chunk_id=ids["chunk"]) == 0


async def test_only_the_questions_of_the_document_s_source_type_are_asked_once(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    other = await _seed(
        async_session, factories.make_signal_question, ids["svc"], source_types=["JOB_POSTING"]
    )

    await _run_job(async_session, ids, FakeGateway())
    await _run_job(async_session, ids, FakeGateway())

    assert await _count(async_session, Classification, question_id=ids["q"]) == 1
    assert await _count(async_session, Classification, question_id=other) == 0


async def test_pairs_are_routed_by_p_positive_and_an_escalation_carries_the_llms_answer(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    middle = await _seed(async_session, factories.make_signal_question, ids["svc"])
    low = await _seed(async_session, factories.make_signal_question, ids["svc"])
    gateway = FakeGateway()
    gateway.p_by_question = {str(ids["q"]): 0.9, str(middle): 0.5, str(low): 0.2}
    gateway.escalations = [_escalation(FindingStrength.MEDIUM)]

    await _run_job(async_session, ids, gateway)

    high_clf = await _one(async_session, Classification, question_id=ids["q"])
    assert (high_clf.status, high_clf.escalated) == (ClassificationStatus.POSITIVE, False)
    middle_clf = await _one(async_session, Classification, question_id=middle)
    assert (middle_clf.status, middle_clf.escalated) == (ClassificationStatus.POSITIVE, True)
    low_clf = await _one(async_session, Classification, question_id=low)
    assert (low_clf.status, low_clf.strength) == (
        ClassificationStatus.NEGATIVE,
        FindingStrength.NONE,
    )
    assert gateway.escalation_calls == 1
    finding = await _one(async_session, Finding, question_id=middle)
    assert (finding.strength, float(finding.confidence), finding.decided_by) == (
        FindingStrength.MEDIUM,
        0.7,
        FindingDecidedBy.LLM,
    )
    assert (await _one(async_session, Finding, question_id=ids["q"])).decided_by == (
        FindingDecidedBy.CLASSIFIER
    )


async def test_the_stored_quote_is_the_passage_span_of_a_normalised_quote(
    async_session: AsyncSession,
) -> None:
    passage = "Lufthansa’s   board — announced a cost-reduction programme targeting EUR 500m."
    ids = await _arrange(async_session, passage=passage)
    gateway = FakeGateway()
    gateway.evidences = [_evidence("Lufthansa's board - announced a cost-reduction programme")]

    await _run_job(async_session, ids, gateway)

    finding = await _one(async_session, Finding, question_id=ids["q"])
    assert finding.quote == "Lufthansa’s   board — announced a cost-reduction programme"


async def test_a_german_finding_has_quote_en(async_session: AsyncSession) -> None:
    ids = await _arrange(async_session, language="de")
    gateway = FakeGateway()
    gateway.evidences = [_evidence(quote_en="Cost-reduction programme")]

    await _run_job(async_session, ids, gateway)

    assert (await _one(async_session, Finding, question_id=ids["q"])).quote_en == (
        "Cost-reduction programme"
    )


async def test_an_english_answer_carrying_quote_en_is_asked_again(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    gateway = FakeGateway()
    gateway.evidences = [_evidence(quote_en="Wrongly translated"), _evidence()]

    await _run_job(async_session, ids, gateway)

    assert gateway.evidence_calls == 2
    assert (await _one(async_session, Finding, question_id=ids["q"])).quote_en is None


async def test_an_evidence_failure_is_retried_once_by_the_next_refresh(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    attempts = _attempts()
    gateway = FakeGateway()
    bad = _evidence("This quote does not appear in the passage at all")
    gateway.evidences = [bad] * (2 * attempts)

    await _run_job(async_session, ids, gateway)
    clf = await _one(async_session, Classification, chunk_id=ids["chunk"])
    assert (clf.status, clf.evidence_retried) == (ClassificationStatus.EVIDENCE_FAILED, False)
    assert gateway.evidence_calls == attempts
    assert await _count(async_session, Finding, question_id=ids["q"]) == 0

    await _run_job(async_session, ids, gateway)
    clf = await _one(async_session, Classification, chunk_id=ids["chunk"])
    assert (clf.status, clf.evidence_retried) == (ClassificationStatus.EVIDENCE_FAILED, True)
    assert gateway.evidence_calls == 2 * attempts

    await _run_job(async_session, ids, gateway)
    assert gateway.evidence_calls == 2 * attempts


async def test_a_success_on_the_retry_writes_the_finding(async_session: AsyncSession) -> None:
    ids = await _arrange(async_session)
    gateway = FakeGateway()
    bad = _evidence("This quote does not appear in the passage at all")
    gateway.evidences = [bad, bad, _evidence()]

    await _run_job(async_session, ids, gateway)
    await _run_job(async_session, ids, gateway)

    clf = await _one(async_session, Classification, chunk_id=ids["chunk"])
    assert clf.status == ClassificationStatus.POSITIVE
    assert (await _one(async_session, Finding, question_id=ids["q"])).quote == QUOTE


async def test_an_escalated_evidence_failure_is_retried_by_escalation(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    attempts = _attempts()
    gateway = FakeGateway(p_positive=0.5)
    invalid = _escalation(FindingStrength.MEDIUM, quote="This quote is not in the passage at all")
    gateway.escalations = [invalid] * attempts

    await _run_job(async_session, ids, gateway)
    assert gateway.escalation_calls == attempts

    gateway.escalations = [_escalation(FindingStrength.MEDIUM)]
    await _run_job(async_session, ids, gateway)

    clf = await _one(async_session, Classification, chunk_id=ids["chunk"])
    assert clf.evidence_retried is True
    assert gateway.escalation_calls == attempts + 1
    assert gateway.evidence_calls == 0
    assert await _count(async_session, Finding, question_id=ids["q"]) == 1


async def test_an_escalation_with_an_invalid_quote_is_asked_again_then_fails_with_its_strength(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    gateway = FakeGateway(p_positive=0.5)
    invalid = _escalation(FindingStrength.MEDIUM, quote="This quote is not in the passage at all")
    gateway.escalations = [invalid, invalid]

    await _run_job(async_session, ids, gateway)

    clf = await _one(async_session, Classification, chunk_id=ids["chunk"])
    assert (clf.status, clf.strength) == (
        ClassificationStatus.EVIDENCE_FAILED,
        FindingStrength.MEDIUM,
    )
    assert gateway.escalation_calls == 2
    assert await _count(async_session, Finding, question_id=ids["q"]) == 0


async def test_an_escalated_choice_answer_naming_an_unknown_option_is_invalid(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(
        async_session,
        question={"answer_type": SignalQuestionAnswerType.CHOICE, "options": OPTIONS},
    )
    gateway = FakeGateway(p_positive=0.5)
    gateway.escalations = [
        _escalation(option_key="UNKNOWN"),
        _escalation(FindingStrength.WEAK, option_key="A"),
    ]

    await _run_job(async_session, ids, gateway)

    finding = await _one(async_session, Finding, question_id=ids["q"])
    assert (finding.option_key, finding.strength) == ("A", FindingStrength.STRONG)
    assert gateway.escalation_calls == 2


async def test_a_choice_finding_carries_its_option_and_observed_at_is_the_publication_date(
    async_session: AsyncSession,
) -> None:
    published = datetime(2026, 9, 1, tzinfo=UTC)
    ids = await _arrange(
        async_session,
        question={"answer_type": SignalQuestionAnswerType.CHOICE, "options": OPTIONS},
        published_at=published,
    )

    await _run_job(async_session, ids, FakeGateway())

    finding = await _one(async_session, Finding, question_id=ids["q"])
    assert (finding.option_key, finding.observed_at, finding.question_revision) == (
        "A",
        published,
        1,
    )


async def test_observed_at_is_the_fetch_time_without_a_publication_date(
    async_session: AsyncSession,
) -> None:
    fetched = datetime(2026, 9, 20, tzinfo=UTC)
    ids = await _arrange(async_session, published_at=None, fetched_at=fetched)

    await _run_job(async_session, ids, FakeGateway())

    assert (await _one(async_session, Finding, question_id=ids["q"])).observed_at == fetched


async def test_an_escalation_stopped_by_the_budget_waits_and_the_next_job_resolves_it(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    gateway = FakeGateway(p_positive=0.5)
    gateway.escalations = [BudgetExhausted(NOW), _escalation()]

    await _run_job(async_session, ids, gateway)

    clf = await _one(async_session, Classification, chunk_id=ids["chunk"])
    assert (clf.status, clf.strength) == (ClassificationStatus.PENDING_LLM, None)
    assert await _count(async_session, Finding, question_id=ids["q"]) == 0
    assert (await _run(async_session, ids)).progress["pending_budget"] == 1

    await _run_job(async_session, ids, gateway)

    clf = await _one(async_session, Classification, chunk_id=ids["chunk"])
    assert clf.status == ClassificationStatus.POSITIVE
    assert await _count(async_session, Finding, question_id=ids["q"]) == 1


async def test_an_unavailable_llm_leaves_the_pair_waiting_and_the_run_records_one_error(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    await _seed(async_session, factories.make_signal_question, ids["svc"])
    gateway = FakeGateway(p_positive=0.5)
    down = UpstreamUnavailable("llm", "ERROR", "down")
    gateway.escalations = [down, down]

    await _run_job(async_session, ids, gateway)

    assert await _count(async_session, Classification, status=ClassificationStatus.PENDING_LLM) == 2
    errors: list[Any] = (await _run(async_session, ids)).errors
    assert [(e["stage"], e["code"]) for e in errors] == [("EVIDENCE", "UPSTREAM_UNAVAILABLE")]


async def test_an_unavailable_classifier_fails_the_job_and_the_next_one_triages(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    gateway = FakeGateway()
    gateway.classify_error = UpstreamUnavailable("classifier", "ERROR", "down")

    with pytest.raises(StepFailed) as failure:
        await _run_job(async_session, ids, gateway)
    assert failure.value.code == "UPSTREAM_UNAVAILABLE"

    await _run_job(async_session, ids, FakeGateway())
    assert await _count(async_session, DocumentTriage, document_id=ids["doc"]) == 1


@pytest.mark.parametrize("call", ["classify", "escalate", "evidence"])
async def test_a_missing_recording_fails_the_job(call: str, async_session: AsyncSession) -> None:
    missing = FixtureMissing("classifier", "key")
    ids = await _arrange(async_session)
    gateway = FakeGateway(p_positive=0.5 if call == "escalate" else 0.9)
    if call == "classify":
        gateway.classify_error = missing
    elif call == "escalate":
        gateway.escalations = [missing]
    else:
        gateway.evidences = [missing]

    with pytest.raises(StepFailed) as failure:
        await _run_job(async_session, ids, gateway)

    assert failure.value.code == "FIXTURE_MISSING"


async def test_a_document_with_an_unembedded_passage_is_not_triaged(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    await _seed(async_session, factories.make_chunk, ids["doc"], ordinal=1, text="More text")

    await _run_job(async_session, ids, FakeGateway())

    assert await _count(async_session, DocumentTriage, document_id=ids["doc"]) == 0


async def test_the_run_progress_holds_what_the_job_created(async_session: AsyncSession) -> None:
    ids = await _arrange(async_session)
    middle = await _seed(async_session, factories.make_signal_question, ids["svc"])
    gateway = FakeGateway()
    gateway.p_by_question = {str(middle): 0.5}
    gateway.escalations = [_escalation()]
    await async_session.execute(
        update(PipelineRun)
        .where(PipelineRun.id == ids["run"])
        .values(progress={"documents_fetched": 4, "findings_created": 1})
    )

    await _run_job(async_session, ids, gateway)

    progress = (await _run(async_session, ids)).progress
    assert progress == {
        "documents_fetched": 4,
        "documents_kept": 1,
        "pairs_classified": 2,
        "pairs_escalated": 1,
        "findings_created": 3,
        "pending_budget": 0,
    }


async def test_findings_of_an_older_revision_become_superseded(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    clf_id = await _seed(
        async_session, factories.make_classification, ids["chunk"], ids["q"], ids["run"]
    )
    finding_id = await _seed(
        async_session,
        factories.make_finding,
        ids["account"],
        ids["q"],
        clf_id,
        ids["chunk"],
    )
    user_id = await _seed(async_session, factories.make_app_user)
    item_id = await _seed(
        async_session,
        factories.make_evaluation_item,
        ids["chunk"],
        ids["q"],
        user_id,
    )

    await supersede_older_revisions(async_session, question_id=ids["q"], current_revision=2)

    finding = await async_session.get(Finding, finding_id)
    assert finding is not None
    await async_session.refresh(finding)
    assert finding.status == FindingStatus.SUPERSEDED
    item = await _one(async_session, EvaluationItem, id=item_id)
    assert item.status == EvaluationItemStatus.STALE


@pytest.mark.parametrize(
    ("has_relevance", "relevance_p", "classified"),
    [(True, 0.9, True), (False, 0.9, True), (False, 0.1, False)],
)
async def test_reclassify_uses_stored_triage_and_only_the_changed_question(
    async_session: AsyncSession,
    has_relevance: bool,
    relevance_p: float,
    classified: bool,
) -> None:
    ids = await _arrange(async_session)
    other_question = await _seed(async_session, factories.make_signal_question, ids["svc"])
    await _seed(
        async_session,
        factories.make_document_triage,
        ids["doc"],
        service_relevance={str(ids["svc"]): 0.9} if has_relevance else {"another": 0.8},
        outcome=DocumentTriageOutcome.KEPT if has_relevance else DocumentTriageOutcome.IRRELEVANT,
    )
    await async_session.execute(
        update(SignalQuestion).where(SignalQuestion.id == ids["q"]).values(revision=2)
    )
    await async_session.execute(
        update(PipelineRun)
        .where(PipelineRun.id == ids["run"])
        .values(
            kind=PipelineRunKind.RECLASSIFY,
            account_id=None,
            service_id=ids["svc"],
            question_id=ids["q"],
        )
    )
    job_id = await _seed(
        async_session,
        factories.make_job,
        ids["run"],
        step=JobStep.SIGNAL,
        payload={"account_id": str(ids["account"])},
    )
    run = await _one(async_session, PipelineRun, id=ids["run"])
    job = await async_session.get(Job, job_id)
    assert job is not None
    gateway = FakeGateway()
    gateway.relevance_p = relevance_p
    async with httpx.AsyncClient() as embedder:
        await run_signal_job(
            async_session,
            job=job,
            run=run,
            settings=WorkerSettings(database_url=SecretStr("postgresql://unused@localhost/unused")),
            gateway=gateway,
            embedder=embedder,
        )
    await async_session.flush()

    assert await _count(
        async_session, Classification, question_id=ids["q"], question_revision=2
    ) == int(classified)
    assert await _count(async_session, Classification, question_id=other_question) == 0
    assert await _count(async_session, DocumentTriage, document_id=ids["doc"]) == 1
    stored = await _one(async_session, DocumentTriage, document_id=ids["doc"])
    if not has_relevance:
        assert stored.service_relevance["another"] == 0.8
        assert stored.service_relevance[str(ids["svc"])] == relevance_p
        assert gateway.requests[0].questions[0].id == f"RELEVANT_{ids['svc']}"
        assert stored.outcome == (
            DocumentTriageOutcome.KEPT if classified else DocumentTriageOutcome.IRRELEVANT
        )
    assert len(gateway.requests) == int(classified) + int(not has_relevance)
    if classified:
        assert gateway.requests[-1].questions[0].id == str(ids["q"])


class FakeEmbedder:
    """`API-67`: every text embeds to the vector `(1, 0, …)`, and every call is recorded."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        texts = json.loads(request.content)["inputs"]
        return httpx.Response(200, json=[[1.0] + [0.0] * 1023 for _ in texts])


@pytest.mark.parametrize("reclassify", [False, True])
async def test_a_long_document_is_classified_only_on_the_selected_passages(
    async_session: AsyncSession,
    reclassify: bool,
) -> None:
    ids = await _arrange(async_session)
    await async_session.execute(delete(Chunk).where(Chunk.document_id == ids["doc"]))
    await async_session.execute(delete(SignalQuestion).where(SignalQuestion.id == ids["q"]))
    question = await _seed(
        async_session, factories.make_signal_question, ids["svc"], hint_terms=["Celonis"]
    )
    ids["q"] = question
    if reclassify:
        await _seed(
            async_session,
            factories.make_document_triage,
            ids["doc"],
            service_relevance={str(ids["svc"]): 0.9},
        )
    chunks: list[uuid.UUID] = []
    for ordinal in range(6):
        text = "Celonis was named." if ordinal == 5 else f"Passage {ordinal} about logistics."
        vector = [1.0 - 0.1 * ordinal, 0.1 * ordinal] + [0.0] * 1022
        chunks.append(
            await _seed(
                async_session,
                factories.make_chunk,
                ids["doc"],
                ordinal=ordinal,
                text=text,
                embedding=vector,
            )
        )
    embedder = FakeEmbedder()

    await _run_job(
        async_session,
        ids,
        FakeGateway(),
        embedder=httpx.AsyncClient(transport=httpx.MockTransport(embedder)),
        reclassify=reclassify,
    )

    classified = set(
        (
            await async_session.execute(
                select(Classification.chunk_id).where(Classification.question_id == question)
            )
        ).scalars()
    )
    assert chunks[5] in classified
    assert len(classified) == 3
    assert embedder.calls == 1


async def test_a_one_passage_document_is_classified_without_calling_the_embedder(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    embedder = FakeEmbedder()

    await _run_job(
        async_session,
        ids,
        FakeGateway(),
        embedder=httpx.AsyncClient(transport=httpx.MockTransport(embedder)),
    )

    assert await _count(async_session, Classification, chunk_id=ids["chunk"]) == 1
    assert embedder.calls == 0


async def test_a_document_marked_a_duplicate_is_neither_triaged_nor_classified(
    async_session: AsyncSession,
) -> None:
    ids = await _arrange(async_session)
    translation = await _seed(
        async_session,
        factories.make_document,
        ids["run"],
        account_id=await async_session.scalar(
            select(Document.account_id).where(Document.id == ids["doc"])
        ),
        text=PASSAGE,
        duplicate_of_id=ids["doc"],
    )
    translation_chunk = await _seed(
        async_session, factories.make_chunk, translation, text=PASSAGE, embedding=VECTOR
    )

    await _run_job(async_session, ids, FakeGateway())

    assert await _count(async_session, DocumentTriage, document_id=ids["doc"]) == 1
    assert await _count(async_session, Classification, chunk_id=ids["chunk"]) == 1
    assert await _count(async_session, DocumentTriage, document_id=translation) == 0
    assert await _count(async_session, Classification, chunk_id=translation_chunk) == 0
