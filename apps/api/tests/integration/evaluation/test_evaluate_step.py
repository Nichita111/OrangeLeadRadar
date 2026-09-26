"""Integration tests of the EVALUATE worker step (`S-EVL-04`, `AC-49`) against a real database,
with a fake OpenRouter transport, per "Tests for the coder" of
`.work/labelling-and-quality/design.md`."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from leadradar.ai.gateway import AiGateway, build_ai_http_client
from leadradar.core.enums import (
    DocumentTriageClassifier,
    EvaluationItemStatus,
    FindingStrength,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
)
from leadradar.db.models.feedback import EvaluationResult
from leadradar.db.models.ingestion import PipelineRun
from leadradar.db.models.signals import Classification, Finding
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import StepFailed
from leadradar.worker.steps.evaluate import run_evaluate_step
from tests.integration import factories

pytestmark = pytest.mark.integration

EVIDENCE_MODEL = "google/gemini-2.5-flash"


def _settings(tmp_path: Path, **overrides: Any) -> WorkerSettings:
    values: dict[str, Any] = {
        "database_url": SecretStr("postgresql://unused"),
        "fixture_mode": "off",
        "fixture_dir": tmp_path / "fixtures",
        "clock_file": tmp_path / "now.txt",
        "openrouter_api_key": SecretStr("test-key"),
        "llm_classifier_model": EVIDENCE_MODEL,
        "llm_evidence_model": EVIDENCE_MODEL,
        "ai_transport_backoff_ms": 0,
        "ai_transport_retries": 0,
        "eval_min_items": 1,
    }
    values.update(overrides)
    return WorkerSettings(**values)


def _gateway(
    settings: WorkerSettings,
    connection: AsyncConnection,
    handler: Callable[[httpx.Request], httpx.Response],
) -> AiGateway:
    sessions = async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    live = httpx.MockTransport(handler)
    return AiGateway(settings, http=build_ai_http_client(settings, live), sessions=sessions)


def _chat_response(content: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.01},
        },
    )


def _schema_name(request: httpx.Request) -> str:
    body = json.loads(request.content)
    name = body["response_format"]["json_schema"]["name"]
    assert isinstance(name, str)
    return name


async def _seed(session: AsyncSession, make: Callable[..., Any], *a: Any, **kw: Any) -> Any:
    return await session.run_sync(lambda s: make(s.connection(), *a, **kw))


async def _arrange(session: AsyncSession, *, second_question: bool = False) -> dict[str, Any]:
    """One passage, one `YES_NO` question with an `ACTIVE` item; optionally a second question on
    the same passage, so `classify` is checked to batch both in one call."""
    service_id = await _seed(session, factories.make_service)
    question_a = await _seed(session, factories.make_signal_question, service_id)
    account_id = await _seed(session, factories.make_account, name="Lufthansa Group")
    fetch_run_id = await _seed(session, factories.make_pipeline_run)
    document_id = await _seed(
        session, factories.make_document, fetch_run_id, account_id=account_id, text="A passage."
    )
    chunk_id = await _seed(session, factories.make_chunk, document_id, text="A passage.")
    user_id = await _seed(session, factories.make_app_user)
    item_a = await _seed(
        session,
        factories.make_evaluation_item,
        chunk_id,
        question_a,
        user_id,
        expected_strength=FindingStrength.STRONG,
        status=EvaluationItemStatus.ACTIVE,
    )
    ids: dict[str, Any] = {
        "service": service_id,
        "question_a": question_a,
        "chunk": chunk_id,
        "item_a": item_a,
    }
    if second_question:
        question_b = await _seed(session, factories.make_signal_question, service_id)
        item_b = await _seed(
            session,
            factories.make_evaluation_item,
            chunk_id,
            question_b,
            user_id,
            expected_strength=FindingStrength.STRONG,
            status=EvaluationItemStatus.ACTIVE,
        )
        ids["question_b"] = question_b
        ids["item_b"] = item_b
    return ids


async def _make_run(session: AsyncSession) -> uuid.UUID:
    run_id: uuid.UUID = await _seed(
        session,
        factories.make_pipeline_run,
        kind=PipelineRunKind.EVALUATION,
        trigger=PipelineRunTrigger.USER,
        status=PipelineRunStatus.RUNNING,
    )
    return run_id


async def _run_row(session: AsyncSession, run_id: uuid.UUID) -> PipelineRun:
    run = await session.get(PipelineRun, run_id)
    assert run is not None
    return run


_HandlerFn = Callable[[httpx.Request], httpx.Response]

_SCALE_HIGH = {"WEAK": 0.1, "MEDIUM": 0.1, "STRONG": 0.8}
_YES_HIGH = {"YES": 0.9, "NO": 0.1}
_SCALE_MID = {"WEAK": 0.3, "MEDIUM": 0.4, "STRONG": 0.3}
_YES_MID = {"YES": 0.5, "NO": 0.5}


def _classify_handler(question_a: uuid.UUID, question_b: uuid.UUID | None) -> _HandlerFn:
    """`question_a`: high `p_positive`, no escalation. `question_b` (when given): mid
    `p_positive`, inside the band, so it is escalated."""

    def handler(request: httpx.Request) -> httpx.Response:
        if _schema_name(request) == "classifier_answers":
            body = json.loads(request.content)
            questions = body["response_format"]["json_schema"]["schema"]["properties"]
            content: dict[str, object] = {}
            for question_id in questions:
                base_id = question_id.removesuffix("__SCALE")
                is_scale = question_id.endswith("__SCALE")
                if base_id == str(question_a):
                    content[question_id] = _SCALE_HIGH if is_scale else _YES_HIGH
                else:
                    content[question_id] = _SCALE_MID if is_scale else _YES_MID
            return _chat_response(content)
        return _chat_response(
            {
                "strength": "WEAK",
                "option_key": None,
                "confidence": 0.55,
                "quote": None,
                "quote_en": None,
                "rationale": None,
            }
        )

    return handler


class TestHappyPath:
    async def test_writes_one_result_with_every_metric_and_no_classification_or_finding(
        self, async_connection: AsyncConnection, async_session: AsyncSession, tmp_path: Path
    ) -> None:
        ids = await _arrange(async_session, second_question=True)
        run_id = await _make_run(async_session)
        run = await _run_row(async_session, run_id)
        settings = _settings(tmp_path)
        ai = _gateway(
            settings, async_connection, _classify_handler(ids["question_a"], ids["question_b"])
        )

        await run_evaluate_step(async_session, run=run, settings=settings, gateway=ai)

        result = (
            await async_session.execute(
                select(EvaluationResult).where(EvaluationResult.run_id == run_id)
            )
        ).scalar_one()
        assert result.items == 2
        assert result.classifier is DocumentTriageClassifier.LLM
        assert set(result.metrics) >= {
            "items",
            "tp",
            "fp",
            "tn",
            "fn",
            "precision",
            "recall",
            "strength_agreement",
            "escalation_rate",
            "classifier_only",
            "per_question",
            "per_source_type",
            "missed_evidence",
            "calibration",
            "errors",
            "lead_verdicts",
        }
        assert (await async_session.execute(select(Classification))).scalars().all() == []
        assert (await async_session.execute(select(Finding))).scalars().all() == []
        per_question = result.metrics["per_question"]
        assert isinstance(per_question, dict)
        assert per_question[str(ids["question_a"])]["service_id"] == str(ids["service"])
        assert per_question[str(ids["question_b"])]["service_id"] == str(ids["service"])

    async def test_calls_the_classifier_once_per_passage_and_the_llm_only_inside_the_band(
        self, async_connection: AsyncConnection, async_session: AsyncSession, tmp_path: Path
    ) -> None:
        ids = await _arrange(async_session, second_question=True)
        run_id = await _make_run(async_session)
        run = await _run_row(async_session, run_id)
        calls = {"classifier_answers": 0, "EscalationOutput": 0}

        base_handler = _classify_handler(ids["question_a"], ids["question_b"])

        def counting_handler(request: httpx.Request) -> httpx.Response:
            calls[_schema_name(request)] = calls.get(_schema_name(request), 0) + 1
            return base_handler(request)

        settings = _settings(tmp_path)
        ai = _gateway(settings, async_connection, counting_handler)

        await run_evaluate_step(async_session, run=run, settings=settings, gateway=ai)

        assert calls["classifier_answers"] == 1  # one passage, one call for both questions
        assert calls["EscalationOutput"] == 1  # only question_b's mid p_positive escalates

    async def test_records_the_configured_classifier_and_the_gate_in_force(
        self, async_connection: AsyncConnection, async_session: AsyncSession, tmp_path: Path
    ) -> None:
        ids = await _arrange(async_session)
        run_id = await _make_run(async_session)
        run = await _run_row(async_session, run_id)
        settings = _settings(
            tmp_path, escalation_lower=0.2, escalation_upper=0.8, eval_min_precision=0.7
        )
        ai = _gateway(settings, async_connection, _classify_handler(ids["question_a"], None))

        await run_evaluate_step(async_session, run=run, settings=settings, gateway=ai)

        result = (
            await async_session.execute(
                select(EvaluationResult).where(EvaluationResult.run_id == run_id)
            )
        ).scalar_one()
        assert result.classifier is DocumentTriageClassifier.LLM
        assert float(result.escalation_lower) == pytest.approx(0.2)
        assert float(result.escalation_upper) == pytest.approx(0.8)
        assert float(result.min_precision) == pytest.approx(0.7)


class TestFailure:
    async def test_a_classifier_failure_raises_step_failed_and_writes_no_result(
        self, async_connection: AsyncConnection, async_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _arrange(async_session)
        run_id = await _make_run(async_session)
        run = await _run_row(async_session, run_id)

        def refuse(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "boom"})

        settings = _settings(tmp_path)
        ai = _gateway(settings, async_connection, refuse)

        with pytest.raises(StepFailed) as excinfo:
            await run_evaluate_step(async_session, run=run, settings=settings, gateway=ai)
        assert excinfo.value.code == "UPSTREAM_UNAVAILABLE"

        remaining = (
            await async_session.execute(
                select(EvaluationResult).where(EvaluationResult.run_id == run_id)
            )
        ).scalar_one_or_none()
        assert remaining is None

    async def test_a_missing_fixture_in_replay_mode_raises_step_failed(
        self, async_connection: AsyncConnection, async_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _arrange(async_session)
        run_id = await _make_run(async_session)
        run = await _run_row(async_session, run_id)
        settings = _settings(tmp_path, fixture_mode="replay")
        assert settings.clock_file is not None
        settings.clock_file.write_text("2026-09-26T12:00:00+00:00")
        ai = _gateway(settings, async_connection, lambda request: httpx.Response(200, json={}))

        with pytest.raises(StepFailed) as excinfo:
            await run_evaluate_step(async_session, run=run, settings=settings, gateway=ai)
        assert excinfo.value.code == "FIXTURE_MISSING"


class TestZeroItems:
    async def test_over_zero_items_writes_a_failing_result_with_null_precision(
        self, async_connection: AsyncConnection, async_session: AsyncSession, tmp_path: Path
    ) -> None:
        run_id = await _make_run(async_session)
        run = await _run_row(async_session, run_id)
        settings = _settings(tmp_path)
        ai = _gateway(settings, async_connection, lambda request: _chat_response({}))

        await run_evaluate_step(async_session, run=run, settings=settings, gateway=ai)

        result = (
            await async_session.execute(
                select(EvaluationResult).where(EvaluationResult.run_id == run_id)
            )
        ).scalar_one()
        assert result.items == 0
        assert result.metrics["precision"] is None
        assert result.passed is False
