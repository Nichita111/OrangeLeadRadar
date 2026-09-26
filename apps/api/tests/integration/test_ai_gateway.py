"""Integration tests of the [AI gateway](/architecture/services/worker.md#ai-gateway) against a
real database, with fake provider transports (`httpx.MockTransport`) and fixture files: one
`AI_CALL` row per call ([Audit actions](/architecture/sql-store.md#audit-actions)), the
[Budget guard](/architecture/rules.md#budget-guard) over those rows (`S-SIG-08`), the classifier
adapter `CLASSIFIER_PROVIDER` selects (`S-SIG-04`), and record then replay under `CLOCK_FILE`
with `FIXTURE_MISSING` for an unrecorded request (`S-RUN-02`)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from leadradar.ai.audit import AiCallContext
from leadradar.ai.errors import BudgetExhausted, UpstreamUnavailable
from leadradar.ai.fixtures import FixtureMissing
from leadradar.ai.gateway import AiGateway, build_ai_http_client
from leadradar.ai.settings import AiGatewaySettings, FixtureMode
from leadradar.ai.shapes import (
    ClassifierQuestion,
    ClassifierRequest,
    EscalationInput,
    EscalationOutput,
    EscalationQuestion,
)
from leadradar.core.enums import (
    AuditEventKind,
    DocumentTriageClassifier,
    SignalQuestionAnswerType,
)
from leadradar.db.models.audit import AuditEvent
from tests.integration import factories as f

pytestmark = pytest.mark.integration

EVIDENCE_MODEL = "google/gemini-2.5-flash"
CLASSIFIER_REQUEST = ClassifierRequest(
    state="DHL Group launches a group-wide cost-reduction programme.",
    context="Company: DHL Group (dhl.com, DE)",
    questions=[
        ClassifierQuestion(id="q1", kind=SignalQuestionAnswerType.YES_NO, text="Cost programme?")
    ],
)
ESCALATION_INPUT = EscalationInput(
    account_name="DHL Group",
    question=EscalationQuestion(
        text="Does the company announce a cost-reduction programme?",
        answer_type=SignalQuestionAnswerType.YES_NO,
        options=None,
    ),
    passage="DHL Group launches a group-wide cost-reduction programme.",
    language="en",
    header="DHL Group · Newsroom",
)
ESCALATION_CONTENT: dict[str, object] = {
    "strength": "STRONG",
    "option_key": None,
    "confidence": 0.9,
    "quote": "DHL Group launches a group-wide cost-reduction programme.",
    "quote_en": None,
    "rationale": "The company announces a cost programme.",
}

Handler = Callable[[httpx.Request], httpx.Response]


def _chat_response(content: dict[str, object], cost: float = 0.01) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 60, "cost": cost},
        },
    )


def _settings(tmp_path: Path, mode: FixtureMode, **overrides: Any) -> AiGatewaySettings:
    values: dict[str, Any] = {
        "fixture_mode": mode,
        "fixture_dir": tmp_path / "fixtures",
        "clock_file": tmp_path / "now.txt",
        "openrouter_api_key": None if mode == "replay" else SecretStr("test-key"),
        "llm_classifier_model": EVIDENCE_MODEL,
        "llm_evidence_model": EVIDENCE_MODEL,
        "ai_transport_backoff_ms": 0,
    }
    values.update(overrides)
    return AiGatewaySettings(**values)


def _gateway(
    settings: AiGatewaySettings, connection: AsyncConnection, handler: Handler | None = None
) -> AiGateway:
    sessions = async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    live = None if handler is None else httpx.MockTransport(handler)
    return AiGateway(settings, http=build_ai_http_client(settings, live), sessions=sessions)


def _refuse(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"No request may be sent: {request.url}")


async def _ai_calls(connection: AsyncConnection) -> list[AuditEvent]:
    async with AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as session:
        rows = await session.execute(
            select(AuditEvent).where(AuditEvent.kind == AuditEventKind.AI_CALL)
        )
        # Seeded spend rows carry no `ai_role`; only the gateway's own rows are returned.
        return [row for row in rows.scalars() if "ai_role" in row.payload]


async def _seed_spend(
    connection: AsyncConnection, *, at: datetime, provider: str, cost_eur: float
) -> None:
    def insert(conn: Connection) -> None:
        f.make_audit_event(
            conn, occurred_at=at, payload={"provider": provider, "cost_eur": cost_eur}
        )

    await connection.run_sync(insert)


async def test_a_jev_call_writes_one_ai_call_row_and_is_not_capped(
    async_connection: AsyncConnection, tmp_path: Path
) -> None:
    run_id = await async_connection.run_sync(lambda conn: f.make_pipeline_run(conn))
    await _seed_spend(async_connection, at=datetime.now(UTC), provider="OPENROUTER", cost_eur=25.0)
    sent: list[dict[str, Any]] = []

    def jev(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "typesafe/jev-1.13",
                "answers": {"q1": {"type": "noul", "noul": 0.9}},
                "usage": {"input_tokens": 50, "output_tokens": 1, "cost": 0.001},
            },
        )

    settings = _settings(tmp_path, "off", classifier_provider=DocumentTriageClassifier.JEV)
    gateway = _gateway(settings, async_connection, jev)
    passage_id = uuid.uuid4()

    answers = await gateway.classify(
        CLASSIFIER_REQUEST, AiCallContext(entity_type="chunk", entity_id=passage_id, run_id=run_id)
    )

    assert gateway.classifier == DocumentTriageClassifier.JEV
    assert answers[0].probabilities == pytest.approx({"YES": 0.9, "NO": 0.1})
    assert sent[0]["model"] == "typesafe/jev-1.13"
    [row] = await _ai_calls(async_connection)
    assert (row.action, row.entity_type, row.entity_id, row.run_id) == (
        "AI_CALL",
        "chunk",
        passage_id,
        run_id,
    )
    payload = dict(row.payload)
    latency_ms = payload.pop("latency_ms")
    assert isinstance(latency_ms, int)
    assert latency_ms >= 0
    assert payload == {
        "ai_role": "CLASSIFIER",
        "provider": "JEV",
        "model": "typesafe/jev-1.13",
        "prompt_version": None,
        "items": 1,
        "input_tokens": 50,
        "output_tokens": 1,
        "cost_eur": pytest.approx(0.001 * 0.92),
        "outcome": "OK",
        "fixture": False,
    }


async def test_an_llm_call_is_refused_once_todays_openrouter_spend_reaches_the_budget(
    async_connection: AsyncConnection, tmp_path: Path
) -> None:
    today = datetime.now(UTC)
    await _seed_spend(async_connection, at=today, provider="OPENROUTER", cost_eur=12.0)
    await _seed_spend(async_connection, at=today, provider="OPENROUTER", cost_eur=8.0)
    gateway = _gateway(_settings(tmp_path, "off"), async_connection, _refuse)

    with pytest.raises(BudgetExhausted) as excinfo:
        await gateway.escalate(ESCALATION_INPUT, AiCallContext())

    tomorrow = today.date() + timedelta(days=1)
    assert excinfo.value.resets_at == datetime(
        tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=UTC
    )
    assert await _ai_calls(async_connection) == []


async def test_jev_costs_and_yesterdays_spend_do_not_count_against_the_budget(
    async_connection: AsyncConnection, tmp_path: Path
) -> None:
    today = datetime.now(UTC)
    await _seed_spend(async_connection, at=today, provider="JEV", cost_eur=100.0)
    await _seed_spend(
        async_connection, at=today - timedelta(days=1), provider="OPENROUTER", cost_eur=100.0
    )
    await _seed_spend(async_connection, at=today, provider="OPENROUTER", cost_eur=19.99)
    gateway = _gateway(
        _settings(tmp_path, "off"),
        async_connection,
        lambda request: _chat_response(ESCALATION_CONTENT),
    )

    output = await gateway.escalate(ESCALATION_INPUT, AiCallContext())

    assert output == EscalationOutput.model_validate(ESCALATION_CONTENT)
    [row] = await _ai_calls(async_connection)
    assert row.payload["provider"] == "OPENROUTER"
    assert row.payload["prompt_version"] == "v1"
    assert row.payload["cost_eur"] == pytest.approx(0.01 * 0.92)


async def test_a_recording_replays_offline_and_the_budget_resets_at_midnight_utc(
    async_connection: AsyncConnection, tmp_path: Path
) -> None:
    recorder = _gateway(
        _settings(tmp_path, "record"),
        async_connection,
        lambda request: _chat_response(ESCALATION_CONTENT),
    )
    recorded = await recorder.escalate(ESCALATION_INPUT, AiCallContext())
    assert list((tmp_path / "fixtures" / "OPENROUTER").glob("*.json"))

    clock_file = tmp_path / "now.txt"
    clock_file.write_text("2026-03-10T23:59:00Z")
    await _seed_spend(
        async_connection,
        at=datetime(2026, 3, 10, 9, tzinfo=UTC),
        provider="OPENROUTER",
        cost_eur=20.0,
    )
    replayer = _gateway(_settings(tmp_path, "replay"), async_connection, _refuse)

    with pytest.raises(BudgetExhausted):
        await replayer.escalate(ESCALATION_INPUT, AiCallContext())

    clock_file.write_text("2026-03-11T00:00:01Z")
    replayed = await replayer.escalate(ESCALATION_INPUT, AiCallContext())

    assert replayed == recorded
    rows = await _ai_calls(async_connection)
    assert sorted(bool(row.payload["fixture"]) for row in rows) == [False, True]
    [replay_row] = [row for row in rows if row.payload["fixture"]]
    assert replay_row.occurred_at == datetime(2026, 3, 11, 0, 0, 1, tzinfo=UTC)


async def test_an_unrecorded_request_fails_with_fixture_missing_and_no_row(
    async_connection: AsyncConnection, tmp_path: Path
) -> None:
    (tmp_path / "now.txt").write_text("2026-03-10T12:00:00Z")
    gateway = _gateway(_settings(tmp_path, "replay"), async_connection, _refuse)

    with pytest.raises(FixtureMissing):
        await gateway.classify(CLASSIFIER_REQUEST, AiCallContext())

    assert await _ai_calls(async_connection) == []


async def test_invalid_output_is_audited_with_its_cost_and_raised(
    async_connection: AsyncConnection, tmp_path: Path
) -> None:
    gateway = _gateway(
        _settings(tmp_path, "off"),
        async_connection,
        lambda request: _chat_response({"strength": "STRONG"}, cost=0.02),
    )

    with pytest.raises(UpstreamUnavailable) as excinfo:
        await gateway.escalate(ESCALATION_INPUT, AiCallContext())

    assert (excinfo.value.dependency, excinfo.value.reason) == ("llm", "INVALID_OUTPUT")
    [row] = await _ai_calls(async_connection)
    assert row.payload["outcome"] == "INVALID_OUTPUT"
    assert row.payload["cost_eur"] == pytest.approx(0.02 * 0.92)


async def test_a_5xx_is_retried_and_the_call_is_audited_once(
    async_connection: AsyncConnection, tmp_path: Path
) -> None:
    attempts: list[int] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503, json={"error": "unavailable"})
        return _chat_response(ESCALATION_CONTENT)

    gateway = _gateway(_settings(tmp_path, "off"), async_connection, flaky)

    await gateway.escalate(ESCALATION_INPUT, AiCallContext())

    assert len(attempts) == 3
    [row] = await _ai_calls(async_connection)
    assert row.payload["outcome"] == "OK"


async def test_a_classifier_timeout_after_its_retries_is_audited_as_timeout(
    async_connection: AsyncConnection, tmp_path: Path
) -> None:
    attempts: list[int] = []

    def slow(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    gateway = _gateway(_settings(tmp_path, "off", ai_transport_retries=1), async_connection, slow)

    with pytest.raises(UpstreamUnavailable) as excinfo:
        await gateway.classify(CLASSIFIER_REQUEST, AiCallContext())

    assert (excinfo.value.dependency, excinfo.value.reason) == ("classifier", "TIMEOUT")
    assert len(attempts) == 2
    [row] = await _ai_calls(async_connection)
    assert row.payload["outcome"] == "TIMEOUT"
    assert row.payload["cost_eur"] == 0.0


async def test_an_unset_key_or_model_is_not_configured_and_sends_nothing(
    async_connection: AsyncConnection, tmp_path: Path
) -> None:
    without_key = _gateway(
        _settings(tmp_path, "off", openrouter_api_key=None), async_connection, _refuse
    )
    without_model = _gateway(
        _settings(tmp_path, "off", llm_evidence_model=None), async_connection, _refuse
    )

    with pytest.raises(UpstreamUnavailable) as key_error:
        await without_key.classify(CLASSIFIER_REQUEST, AiCallContext())
    with pytest.raises(UpstreamUnavailable) as model_error:
        await without_model.escalate(ESCALATION_INPUT, AiCallContext())

    assert (key_error.value.dependency, key_error.value.reason) == ("classifier", "NOT_CONFIGURED")
    assert (model_error.value.dependency, model_error.value.reason) == ("llm", "NOT_CONFIGURED")
    assert await _ai_calls(async_connection) == []
