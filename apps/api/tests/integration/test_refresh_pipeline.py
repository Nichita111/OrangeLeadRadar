"""A whole `ACCOUNT_REFRESH` through the real job loop, from `FETCH` through `PROCESS` and
`SIGNAL` to `SCORE` ([FL-07](/features/signal-pipeline.md#fl-07-refresh-one-account); `S-SIG-01`
to `S-SIG-06`, `S-SIG-09`, `N-05`).

The provider's side is a `Web` behind the real crawl client, the embedder an `httpx.MockTransport`
and the AI gateway a fake that answers by markers in the text it is given."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from leadradar.ai.audit import AiCallContext
from leadradar.ai.gateway import AiGateway
from leadradar.ai.shapes import (
    ClassifierAnswer,
    ClassifierRequest,
    EscalationInput,
    EscalationOutput,
    EvidenceInput,
    EvidenceOutput,
)
from leadradar.core.enums import (
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AuditAction,
    ClassificationStatus,
    DocumentTriageClassifier,
    DocumentTriageOutcome,
    FindingStrength,
    JobStatus,
    JobStep,
    PipelineRunStatus,
    ScoringConfigStatus,
    SourcePluginCode,
)
from leadradar.core.signal.triage import ABOUT_ACCOUNT_QUESTION_ID
from leadradar.db.models.accounts import AccountAlias, AccountSource
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.configuration import SignalQuestion
from leadradar.db.models.ingestion import Chunk, Document, Job, PipelineRun, SourcePlugin
from leadradar.db.models.signals import AccountScore, Classification, DocumentTriage, Finding
from leadradar.worker.loop import process_next_job
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import STEP_HANDLERS
from tests.integration import factories as f
from tests.integration.pipeline_doubles import (
    GDELT_SEARCH,
    T0,
    Clock,
    Embedder,
    Web,
    feed,
    gdelt_articles,
    html,
    install_web,
    session_factory,
    vec,
)

pytestmark = pytest.mark.integration

TRANSLATION = "Translated story"
ORIGINAL = "First story"
MENTION = "Second story"
OWN = "Own news"
HIGH = "High question"
MIDDLE = "Middle question"
#: p_positive by (document marker, question text)
P_POSITIVE = {
    (ORIGINAL, HIGH): 0.9,
    (ORIGINAL, MIDDLE): 0.5,
    (OWN, HIGH): 0.9,
    (OWN, MIDDLE): 0.2,
}


class ScriptedGateway:
    """Answers by the markers in the request: the document's topic and the question's text."""

    @property
    def classifier(self) -> DocumentTriageClassifier:
        return DocumentTriageClassifier.JEV

    async def classify(
        self, request: ClassifierRequest, context: AiCallContext
    ) -> list[ClassifierAnswer]:
        marker = next(m for m in (ORIGINAL, MENTION, OWN) if m in request.state)
        answers = []
        for question in request.questions:
            if question.id == ABOUT_ACCOUNT_QUESTION_ID:
                yes = 0.1 if marker == MENTION else 0.9
                probs = {"YES": yes, "NO": 1 - yes}
            elif question.id.startswith("RELEVANT_"):
                probs = {"YES": 0.9, "NO": 0.1}
            elif question.id.endswith("__SCALE"):
                probs = {"WEAK": 0.0, "MEDIUM": 0.0, "STRONG": 1.0}
            else:
                text = HIGH if HIGH in question.text else MIDDLE
                yes = P_POSITIVE[(marker, text)]
                probs = {"YES": yes, "NO": 1 - yes}
            answers.append(ClassifierAnswer(question_id=question.id, probabilities=probs))
        return answers

    @staticmethod
    def _quote(passage: str) -> str:
        marker = next(m for m in (ORIGINAL, OWN) if m in passage)
        return f"{marker} announced a new logistics hub this quarter"

    async def escalate(
        self, role_input: EscalationInput, context: AiCallContext
    ) -> EscalationOutput:
        return EscalationOutput(
            strength=FindingStrength.MEDIUM,
            option_key=None,
            confidence=0.7,
            quote=self._quote(role_input.passage),
            quote_en=None,
            rationale="Announces a hub.",
        )

    async def extract_evidence(
        self, role_input: EvidenceInput, context: AiCallContext
    ) -> EvidenceOutput:
        return EvidenceOutput(
            quote=self._quote(role_input.passage), quote_en=None, rationale="Announces a hub."
        )


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> Web:
    return install_web(monkeypatch)


@pytest.fixture
async def connection(async_connection: AsyncConnection) -> AsyncIterator[AsyncConnection]:
    await async_connection.execute(
        update(Job)
        .where(Job.status.in_((JobStatus.READY, JobStatus.RUNNING)))
        .values(status=JobStatus.CANCELLED)
    )
    await async_connection.execute(delete(SourcePlugin))
    yield async_connection


class Scene:
    def __init__(self, account_id: uuid.UUID, service_id: uuid.UUID, question_key: str) -> None:
        self.account_id = account_id
        self.service_id = service_id
        self.question_key = question_key


def _arrange(conn: Connection) -> Scene:
    for code in SourcePluginCode:
        f.make_source_plugin(conn, code=code)
    account_id = f.make_account(conn, name="Acme Corp", domain="acme-test.com")
    conn.execute(
        insert(AccountAlias),
        [{"account_id": account_id, "alias": a, "normalised": a.lower()} for a in ("Acme Corp",)],
    )
    conn.execute(
        insert(AccountSource).values(
            account_id=account_id,
            kind=AccountSourceKind.RSS_FEED,
            url="https://acme-test.com/feed.xml",
            origin=AccountSourceOrigin.MANUAL,
            status=AccountSourceStatus.ACTIVE,
        )
    )
    service_id = f.make_service(conn)
    high = f.make_signal_question(
        conn, service_id, text=HIGH, source_types=["NEWS", "COMPANY_PUBLICATION"]
    )
    f.make_signal_question(
        conn, service_id, text=MIDDLE, source_types=["NEWS", "COMPANY_PUBLICATION"]
    )
    key = conn.execute(select(SignalQuestion.key).where(SignalQuestion.id == high)).scalar_one()
    f.make_scoring_config(
        conn,
        service_id,
        status=ScoringConfigStatus.ACTIVE,
        settings={"questions": [{"question_key": key, "weight": "HIGH"}]},
    )
    return Scene(account_id, service_id, key)


def _start_refresh(conn: Connection, account_id: uuid.UUID) -> uuid.UUID:
    run_id = f.make_pipeline_run(conn, account_id=account_id)
    for code in (SourcePluginCode.GDELT, SourcePluginCode.RSS):
        f.make_job(
            conn,
            run_id,
            step=JobStep.FETCH,
            payload={"plugin_code": code.value},
            not_before=T0,
        )
    return run_id


async def _drain(connection: AsyncConnection, embedder: Embedder, clock: Clock) -> None:
    worker_settings = WorkerSettings(
        database_url=SecretStr("postgresql://unused"),
        crawler_user_agent="LeadRadar-test/1.0",
        job_max_attempts=1,
        job_retry_backoff_s=1,
    )
    async with embedder.client() as client:
        while await process_next_job(
            session_factory(connection),
            handlers=STEP_HANDLERS,
            settings=worker_settings,
            clock=clock,
            worker_id="worker-1",
            gateway=cast(AiGateway, ScriptedGateway()),
            embedder=client,
        ):
            pass


async def _count(connection: AsyncConnection, model: Any) -> int:
    return int(await connection.scalar(select(func.count()).select_from(model)) or 0)


async def test_a_refresh_runs_from_fetch_to_score_and_a_second_one_creates_nothing(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(
        GDELT_SEARCH,
        gdelt_articles(
            [
                "https://news.example.org/t",
                "https://news.example.org/o",
                "https://news.example.org/m",
            ]
        ),
        kind="json",
    )
    web.add("https://news.example.org/t", html(TRANSLATION))
    web.add("https://news.example.org/o", html(ORIGINAL))
    web.add("https://news.example.org/m", html(MENTION))
    web.add(
        "https://acme-test.com/feed.xml",
        feed([("https://acme-test.com/news/one", html(OWN))]),
        kind="xml",
    )
    scene = await connection.run_sync(_arrange)
    run_id = await connection.run_sync(lambda c: _start_refresh(c, scene.account_id))
    embedder = Embedder(
        markers={
            TRANSLATION: vec(1.0, 0.001),
            ORIGINAL: vec(1.0),
            MENTION: vec(0.0, 1.0),
            OWN: vec(0.0, 0.0, 1.0),
        }
    )
    clock = Clock()

    await _drain(connection, embedder, clock)

    rows = (await connection.execute(select(Document))).all()
    assert len(rows) == 4
    chunks = (await connection.execute(select(Chunk))).all()
    assert all(chunk.embedding is not None for chunk in chunks)

    duplicates = [d for d in rows if d.duplicate_of_id is not None]
    assert [TRANSLATION in d.text for d in duplicates] == [True]
    triaged = {t.document_id: t for t in (await connection.execute(select(DocumentTriage))).all()}
    assert set(triaged) == {d.id for d in rows if d.duplicate_of_id is None}
    by_marker = {m: d for d in rows for m in (ORIGINAL, MENTION, OWN) if m in d.text}
    assert triaged[by_marker[MENTION].id].outcome == DocumentTriageOutcome.NOT_ABOUT_ACCOUNT
    assert all(t.classifier == DocumentTriageClassifier.JEV for t in triaged.values())

    chunk_of = {c.document_id: c for c in chunks}
    classifications = (await connection.execute(select(Classification))).all()
    assert chunk_of[by_marker[MENTION].id].id not in {c.chunk_id for c in classifications}
    assert sorted((c.status.value, c.escalated) for c in classifications) == [
        ("NEGATIVE", False),
        ("POSITIVE", False),
        ("POSITIVE", False),
        ("POSITIVE", True),
    ]
    assert {c.classifier for c in classifications} == {DocumentTriageClassifier.JEV}
    assert all(c.status is not ClassificationStatus.PENDING_LLM for c in classifications)

    findings = (await connection.execute(select(Finding))).all()
    assert len(findings) == 3
    document_of_chunk = {c.id: c.document_id for c in chunks}
    text_of = {d.id: d for d in rows}
    for finding in findings:
        document = text_of[document_of_chunk[finding.chunk_id]]
        assert finding.quote in chunk_of[document.id].text
        assert finding.quote_en is None
        assert finding.observed_at == (document.published_at or document.fetched_at)

    current = (
        await connection.execute(
            select(AccountScore).where(
                AccountScore.account_id == scene.account_id,
                AccountScore.service_id == scene.service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).all()
    assert len(current) == 1

    run = (
        await connection.execute(
            select(PipelineRun.status, PipelineRun.progress).where(PipelineRun.id == run_id)
        )
    ).one()
    assert run.status is PipelineRunStatus.SUCCEEDED
    assert run.progress["documents_fetched"] == 4
    assert {
        k: run.progress[k]
        for k in ("documents_kept", "pairs_classified", "pairs_escalated", "findings_created")
    } == {
        "documents_kept": 2,
        "pairs_classified": 4,
        "pairs_escalated": 1,
        "findings_created": 3,
    }
    finished = await connection.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.run_id == run_id, AuditEvent.action == AuditAction.RUN_FINISHED)
    )
    assert finished == 1

    before = [
        await _count(connection, model)
        for model in (Document, DocumentTriage, Classification, Finding, AccountScore)
    ]
    clock.now += timedelta(hours=1)
    await connection.run_sync(lambda c: _start_refresh(c, scene.account_id))

    await _drain(connection, embedder, clock)

    assert [
        await _count(connection, model)
        for model in (Document, DocumentTriage, Classification, Finding, AccountScore)
    ] == before
