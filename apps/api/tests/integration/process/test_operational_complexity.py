"""Integration tests of `PROCESS`'s operational-complexity classification ([Account attributes]
(/architecture/rules.md#account-attributes); `S-ING-06`, `AC-69` operational-complexity half,
decision G2/G3 of `adr-21-source-detection-timing-and-crawler-redirects`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from leadradar.ai.audit import AiCallContext
from leadradar.ai.gateway import AiGateway
from leadradar.ai.shapes import ClassifierAnswer, ClassifierRequest
from leadradar.core.enums import (
    AccountOperationalComplexity,
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AuditAction,
    JobStatus,
    JobStep,
    SourcePluginCode,
)
from leadradar.db.models.accounts import Account, AccountSource
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.ingestion import Job
from leadradar.worker.loop import process_next_job
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import STEP_HANDLERS, StepContext, StepHandler
from tests.integration import factories as f
from tests.integration.pipeline_doubles import T0, Clock, Embedder, session_factory

pytestmark = pytest.mark.integration

DOMAIN = "acme-test.com"
HOME_URL = f"https://{DOMAIN}/"


class _FakeGateway:
    """Answers the one-question operational-complexity request with a fixed distribution."""

    def __init__(self, probabilities: dict[str, float]) -> None:
        self.probabilities = probabilities
        self.calls = 0

    async def classify(
        self, request: ClassifierRequest, context: AiCallContext
    ) -> list[ClassifierAnswer]:
        self.calls += 1
        [question] = request.questions
        return [ClassifierAnswer(question_id=question.id, probabilities=self.probabilities)]


def settings(**overrides: Any) -> WorkerSettings:
    values: dict[str, Any] = {
        "database_url": SecretStr("postgresql://unused"),
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


async def _account_with_website_document(
    connection: AsyncConnection,
    *,
    text: str,
    complexity: AccountOperationalComplexity | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    def build(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        account_id = f.make_account(
            conn,
            name="Acme Corp",
            domain=DOMAIN,
            operational_complexity=complexity,
            attribute_origin={} if complexity is None else {"operational_complexity": "MANUAL"},
        )
        conn.execute(
            insert(AccountSource).values(
                account_id=account_id,
                kind=AccountSourceKind.WEBSITE,
                url=HOME_URL,
                origin=AccountSourceOrigin.MANUAL,
                status=AccountSourceStatus.ACTIVE,
            )
        )
        run_id = f.make_pipeline_run(conn, account_id=account_id)
        f.make_document(
            conn,
            run_id,
            account_id=account_id,
            plugin_code=SourcePluginCode.WEBSITE,
            url=HOME_URL,
            text=text,
        )
        f.make_job(conn, run_id, step=JobStep.PROCESS, not_before=T0, priority=7)
        return account_id, run_id

    return await connection.run_sync(build)


async def _drain(connection: AsyncConnection, gateway: object) -> None:
    handlers: dict[JobStep, StepHandler] = {JobStep.PROCESS: STEP_HANDLERS[JobStep.PROCESS]}

    async def _succeed(context: StepContext) -> None:
        return None

    handlers[JobStep.SIGNAL] = _succeed
    handlers[JobStep.SCORE] = _succeed
    async with Embedder().client() as embedder:
        while await process_next_job(
            session_factory(connection),
            handlers=handlers,
            settings=settings(),
            clock=Clock(),
            worker_id="worker-1",
            gateway=cast(AiGateway, gateway),
            embedder=embedder,
        ):
            pass


async def test_a_null_complexity_is_classified_and_written_with_one_audit_row(
    connection: AsyncConnection,
) -> None:
    account_id, run_id = await _account_with_website_document(
        connection, text="A" * 300, complexity=None
    )
    gateway = _FakeGateway({"LOW": 0.1, "MEDIUM": 0.8, "HIGH": 0.1})

    await _drain(connection, gateway)

    assert gateway.calls == 1
    account = (
        await connection.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    assert account.operational_complexity is AccountOperationalComplexity.MEDIUM
    assert account.attribute_origin["operational_complexity"] == "CLASSIFIER"
    [audit_row] = (
        await connection.execute(
            select(AuditEvent).where(
                AuditEvent.run_id == run_id, AuditEvent.action == AuditAction.ACCOUNT_UPDATED
            )
        )
    ).all()
    assert audit_row.actor_id is None


async def test_a_manual_value_causes_no_classifier_call(connection: AsyncConnection) -> None:
    await _account_with_website_document(
        connection, text="A" * 300, complexity=AccountOperationalComplexity.HIGH
    )
    gateway = _FakeGateway({"LOW": 1.0, "MEDIUM": 0.0, "HIGH": 0.0})

    await _drain(connection, gateway)

    assert gateway.calls == 0
