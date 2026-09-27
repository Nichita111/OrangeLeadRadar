"""A service created, questioned and activated purely through the configuration commands is
triaged, classified and scored by the next account refresh like any seeded service — no code
path names a service ([N-11](/requirements/system.md) "configuration only";
[FL-01](/features/service-configuration.md#fl-01-define-a-service-and-its-signal-questions);
[Triage](/architecture/rules.md#triage); [Rescoring](/architecture/rules.md#rescoring))."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from leadradar.ai.gateway import AiGateway
from leadradar.configuration.commands import create_question, create_service
from leadradar.core.enums import (
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    ClassificationStatus,
    DocumentSourceType,
    DocumentTriageOutcome,
    JobStatus,
    JobStep,
    ScoringConfigStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SourcePluginCode,
)
from leadradar.core.signal.triage import RELEVANT_QUESTION_PREFIX
from leadradar.db.models.accounts import AccountAlias, AccountSource
from leadradar.db.models.configuration import ScoringConfig, SignalQuestion
from leadradar.db.models.ingestion import Job, SourcePlugin
from leadradar.db.models.signals import AccountScore, Classification, DocumentTriage, Finding
from leadradar.scoring.activate import activate_scoring_config
from leadradar.worker.loop import process_next_job
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import STEP_HANDLERS
from tests.integration import factories as f
from tests.integration.pipeline_doubles import (
    GDELT_SEARCH,
    T0,
    Clock,
    Embedder,
    ScriptedGateway,
    Web,
    feed,
    gdelt_articles,
    html,
    install_web,
    session_factory,
)

pytestmark = pytest.mark.integration

HIGH = "High question"
MIDDLE = "Middle question"
OWN = "Own news"


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
    def __init__(
        self, account_id: uuid.UUID, service1_id: uuid.UUID, service2_id: uuid.UUID
    ) -> None:
        self.account_id = account_id
        self.service1_id = service1_id
        self.service2_id = service2_id


def _scene(conn: Connection) -> Scene:
    """An account with one own (RSS) source, and two already-active seeded services: one with a
    `HIGH`-weighted question, one with a `MEDIUM`-weighted one, both able to classify the
    account's RSS document."""
    for code in SourcePluginCode:
        f.make_source_plugin(conn, code=code)
    account_id = f.make_account(conn, name="Acme Corp", domain="acme-test.com")
    conn.execute(
        insert(AccountAlias),
        [{"account_id": account_id, "alias": "Acme Corp", "normalised": "acme corp"}],
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

    service1_id = f.make_service(conn)
    q1 = f.make_signal_question(
        conn, service1_id, text=HIGH, source_types=["NEWS", "COMPANY_PUBLICATION"]
    )
    key1 = conn.execute(select(SignalQuestion.key).where(SignalQuestion.id == q1)).scalar_one()
    f.make_scoring_config(
        conn,
        service1_id,
        status=ScoringConfigStatus.ACTIVE,
        settings={"questions": [{"question_key": key1, "weight": "HIGH"}]},
    )

    service2_id = f.make_service(conn)
    q2 = f.make_signal_question(
        conn, service2_id, text=MIDDLE, source_types=["NEWS", "COMPANY_PUBLICATION"]
    )
    key2 = conn.execute(select(SignalQuestion.key).where(SignalQuestion.id == q2)).scalar_one()
    f.make_scoring_config(
        conn,
        service2_id,
        status=ScoringConfigStatus.ACTIVE,
        settings={"questions": [{"question_key": key2, "weight": "MEDIUM"}]},
    )

    return Scene(account_id, service1_id, service2_id)


def _start_refresh(conn: Connection, account_id: uuid.UUID) -> uuid.UUID:
    run_id = f.make_pipeline_run(conn, account_id=account_id)
    for code in (SourcePluginCode.GDELT, SourcePluginCode.RSS):
        f.make_job(
            conn, run_id, step=JobStep.FETCH, payload={"plugin_code": code.value}, not_before=T0
        )
    return run_id


async def _drain(connection: AsyncConnection, embedder: Embedder, gateway: ScriptedGateway) -> None:
    worker_settings = WorkerSettings(
        database_url=SecretStr("postgresql://unused"),
        crawler_user_agent="LeadRadar-test/1.0",
        job_max_attempts=1,
        job_retry_backoff_s=1,
    )
    clock = Clock()
    async with embedder.client() as client:
        while await process_next_job(
            session_factory(connection),
            handlers=STEP_HANDLERS,
            settings=worker_settings,
            clock=clock,
            worker_id="worker-1",
            gateway=cast(AiGateway, gateway),
            embedder=client,
        ):
            pass


async def _create_third_service(
    connection: AsyncConnection, actor_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """`create_service` (`API-08`), `create_question` twice with different source types
    (`API-12`); returns the service id and its two question ids. Activation is the caller's
    choice."""
    session = session_factory(connection)()
    service = await create_service(
        session,
        code=f"THIRD_{uuid.uuid4().hex[:8].upper()}",
        name=f"Third service {uuid.uuid4().hex[:8]}",
        description="A third service, configured only through the API.",
        value_proposition="A value proposition.",
        actor_id=actor_id,
        now=T0,
    )
    news_question = await create_question(
        session,
        service_id=service.id,
        key="NEWS_QUESTION",
        text=HIGH,
        answer_type=SignalQuestionAnswerType.YES_NO,
        options=None,
        polarity=SignalQuestionPolarity.POSITIVE,
        source_types=[DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION],
        hint_terms=[],
        actor_id=actor_id,
        now=T0,
    )
    job_question = await create_question(
        session,
        service_id=service.id,
        key="JOB_QUESTION",
        text=MIDDLE,
        answer_type=SignalQuestionAnswerType.YES_NO,
        options=None,
        polarity=SignalQuestionPolarity.POSITIVE,
        source_types=[DocumentSourceType.JOB_POSTING],
        hint_terms=[],
        actor_id=actor_id,
        now=T0,
    )
    return service.id, news_question.id, job_question.id


async def _activate(
    connection: AsyncConnection, service_id: uuid.UUID, actor_id: uuid.UUID
) -> uuid.UUID:
    session = session_factory(connection)()
    draft_id = (
        await session.execute(
            select(ScoringConfig.id).where(
                ScoringConfig.service_id == service_id,
                ScoringConfig.status == ScoringConfigStatus.DRAFT,
            )
        )
    ).scalar_one()
    activation = await activate_scoring_config(
        session, config_id=draft_id, actor_id=actor_id, change_note="Activate v1", now=T0
    )
    return activation.id


async def _classifications_by_question(connection: AsyncConnection, service_id: uuid.UUID) -> Any:
    rows = await connection.execute(
        select(Classification)
        .join(SignalQuestion, SignalQuestion.id == Classification.question_id)
        .where(SignalQuestion.service_id == service_id)
    )
    return rows.all()


async def test_third_service_classified_and_scored_by_the_next_refresh(
    connection: AsyncConnection, web: Web
) -> None:
    """A service created, questioned and activated through configuration is triaged, classified
    and scored by the next refresh like the two seeded services."""
    web.add(GDELT_SEARCH, gdelt_articles([]), kind="json")
    web.add(
        "https://acme-test.com/feed.xml",
        feed([("https://acme-test.com/news/one", html(OWN))]),
        kind="xml",
    )

    scene = await connection.run_sync(_scene)
    actor_id = await connection.run_sync(f.make_app_user)
    service3_id, news_question_id, job_question_id = await _create_third_service(
        connection, actor_id
    )
    activated_config_id = await _activate(connection, service3_id, actor_id)

    await connection.run_sync(lambda c: _start_refresh(c, scene.account_id))
    embedder = Embedder(markers={OWN: [1.0] + [0.0] * 1023})
    gateway = ScriptedGateway()

    await _drain(connection, embedder, gateway)

    triage_requests = [
        request
        for request in gateway.requests
        if sum(1 for q in request.questions if q.id.startswith(RELEVANT_QUESTION_PREFIX)) == 3
    ]
    assert len(triage_requests) == 1
    relevant_ids = {
        q.id for q in triage_requests[0].questions if q.id.startswith(RELEVANT_QUESTION_PREFIX)
    }
    assert relevant_ids == {
        f"{RELEVANT_QUESTION_PREFIX}{scene.service1_id}",
        f"{RELEVANT_QUESTION_PREFIX}{scene.service2_id}",
        f"{RELEVANT_QUESTION_PREFIX}{service3_id}",
    }

    [triage_row] = (await connection.execute(select(DocumentTriage))).all()
    assert triage_row.outcome is DocumentTriageOutcome.KEPT
    assert triage_row.service_relevance[str(service3_id)] == pytest.approx(0.9)

    classifications = (await connection.execute(select(Classification))).all()
    third_news = [c for c in classifications if c.question_id == news_question_id]
    third_job = [c for c in classifications if c.question_id == job_question_id]
    assert [(c.question_revision, c.status.value) for c in third_news] == [(1, "POSITIVE")]
    assert third_job == []  # no JOB_POSTING document exists to pair it with
    assert all(c.status is not ClassificationStatus.PENDING_LLM for c in classifications)

    findings = (await connection.execute(select(Finding))).all()
    assert any(finding.question_id == news_question_id for finding in findings)

    current_scores = (
        await connection.execute(
            select(AccountScore).where(
                AccountScore.account_id == scene.account_id,
                AccountScore.service_id == service3_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).all()
    assert len(current_scores) == 1
    assert current_scores[0].scoring_config_id == activated_config_id

    service1_classifications = await _classifications_by_question(connection, scene.service1_id)
    service2_classifications = await _classifications_by_question(connection, scene.service2_id)
    assert [c.status.value for c in service1_classifications] == ["POSITIVE"]
    assert [c.status.value for c in service2_classifications] == ["NEGATIVE"]


async def test_a_new_service_is_classified_but_not_scored_before_its_first_activation(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(GDELT_SEARCH, gdelt_articles([]), kind="json")
    web.add(
        "https://acme-test.com/feed.xml",
        feed([("https://acme-test.com/news/one", html(OWN))]),
        kind="xml",
    )

    scene = await connection.run_sync(_scene)
    actor_id = await connection.run_sync(f.make_app_user)
    service3_id, news_question_id, _job_question_id = await _create_third_service(
        connection, actor_id
    )
    # No activation: the service stays on its DRAFT scoring config.

    await connection.run_sync(lambda c: _start_refresh(c, scene.account_id))
    embedder = Embedder(markers={OWN: [1.0] + [0.0] * 1023})
    gateway = ScriptedGateway()

    await _drain(connection, embedder, gateway)

    classifications = (
        await connection.execute(
            select(Classification).where(Classification.question_id == news_question_id)
        )
    ).all()
    assert [(c.question_revision, c.status.value) for c in classifications] == [(1, "POSITIVE")]

    scores = (
        await connection.execute(
            select(AccountScore).where(
                AccountScore.account_id == scene.account_id, AccountScore.service_id == service3_id
            )
        )
    ).all()
    assert scores == []
