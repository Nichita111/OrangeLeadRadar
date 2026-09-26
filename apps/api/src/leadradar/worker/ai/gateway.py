"""[AI gateway](/architecture/services/worker.md#ai-gateway): fixture layer + port functions.

``API-62`` classify, ``API-63`` escalate, ``API-64`` extract_evidence — all in ``replay``
fixture mode only for this task.  Live adapters (Jev, OpenRouter) are wired in a later task.

Fixture key: SHA-256 of ``adapter_name + ":" + canonical_json(request)``, where
``canonical_json`` is ``json.dumps(request, sort_keys=True, separators=(',', ':'))``.

Each call writes one ``AI_CALL`` audit row via the caller-supplied session.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AuditEventKind
from leadradar.db.models.audit import AuditEvent
from leadradar.worker.ai.classifier import ClassifierAnswer, ClassifierRequest
from leadradar.worker.ai.llm import (
    EscalationInput,
    EscalationOutput,
    EvidenceInput,
    EvidenceOutput,
)

# ── Errors ─────────────────────────────────────────────────────────────────────


class FixtureMissingError(Exception):
    """No fixture file found for this request key (FIXTURE_MISSING)."""


class InvalidOutputError(Exception):
    """The fixture payload fails the port's output validation (INVALID_OUTPUT)."""


class BudgetExhaustedError(Exception):
    """The daily LLM budget has been exhausted (BUDGET_EXHAUSTED)."""


# ── Fixture helpers ────────────────────────────────────────────────────────────


def _fixture_key(adapter_name: str, request: dict[str, Any]) -> str:
    """SHA-256 of ``adapter_name + ':' + canonical_json(request)``."""
    payload = adapter_name + ":" + json.dumps(request, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_fixture(fixture_dir: str, key: str) -> dict[str, Any]:
    """Load a fixture JSON file by its SHA-256 key.  Raises ``FixtureMissingError``."""
    path = Path(fixture_dir) / f"{key}.json"
    if not path.exists():
        raise FixtureMissingError(f"fixture not found: {path}")
    with path.open() as f:
        data: dict[str, Any] = json.load(f)
    return data


# ── Budget guard ───────────────────────────────────────────────────────────────


async def _check_budget(
    session: AsyncSession,
    daily_budget_eur: float,
) -> None:
    """Raise ``BudgetExhaustedError`` when today's LLM spend has reached the cap.

    [Budget guard](/architecture/rules.md#budget-guard): sums ``cost_eur`` of today's
    ``AI_CALL`` rows with provider ``OPENROUTER``.
    """
    from sqlalchemy import func, select, text

    # Sum cost_eur for today's OPENROUTER AI_CALL rows
    stmt = (
        select(func.coalesce(func.sum(text("(payload->>'cost_eur')::numeric")), 0))
        .select_from(AuditEvent.__table__)
        .where(
            AuditEvent.__table__.c.kind == AuditEventKind.AI_CALL.value,
            AuditEvent.__table__.c.occurred_at >= _today_utc_start(),
            text("payload->>'provider' = 'OPENROUTER'"),
        )
    )
    result = await session.execute(stmt)
    total_eur: float = float(result.scalar_one() or 0)
    if total_eur >= daily_budget_eur:
        raise BudgetExhaustedError(
            f"daily LLM budget exhausted: {total_eur:.4f} EUR >= {daily_budget_eur:.4f} EUR"
        )


def _today_utc_start() -> datetime:
    now = datetime.now(tz=UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


# ── Audit helper ───────────────────────────────────────────────────────────────


async def _write_ai_call_audit(
    session: AsyncSession,
    *,
    run_id: uuid.UUID | None,
    entity_id: uuid.UUID | None,
    ai_role: str,
    provider: str,
    model: str | None,
    prompt_version: str | None,
    items: int,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_eur: float,
    latency_ms: int,
    outcome: str,
    fixture: bool,
) -> None:
    """Insert one ``AI_CALL`` audit row.

    Payload follows [Audit actions](/architecture/sql-store.md#audit-actions).
    """
    session.add(
        AuditEvent(
            occurred_at=datetime.now(tz=UTC),
            actor_id=None,
            kind=AuditEventKind.AI_CALL,
            action="AI_CALL",
            entity_type=None,
            entity_id=entity_id,
            run_id=run_id,
            request_id=None,
            payload={
                "ai_role": ai_role,
                "provider": provider,
                "model": model,
                "prompt_version": prompt_version,
                "items": items,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_eur": cost_eur,
                "latency_ms": latency_ms,
                "outcome": outcome,
                "fixture": fixture,
            },
        )
    )


# ── Public port functions ──────────────────────────────────────────────────────


async def classify(
    request: ClassifierRequest,
    *,
    session: AsyncSession,
    fixture_mode: str,
    fixture_dir: str,
    run_id: uuid.UUID | None = None,
    usd_eur_rate: float = 0.92,
) -> list[ClassifierAnswer]:
    """[``API-62``](/architecture/interfaces.md#classifier): classify one passage.

    In ``replay`` mode: loads the fixture, validates each answer, writes one
    ``AI_CALL`` audit row with role ``CLASSIFIER``, and returns the answers.

    A missing fixture raises ``FixtureMissingError`` (mapped to ``FIXTURE_MISSING``).
    An answer whose probabilities do not sum to 1 ± 0.001 raises ``InvalidOutputError``.
    """
    if fixture_mode != "replay":
        raise RuntimeError(f"classify() only supports fixture_mode='replay'; got {fixture_mode!r}")

    req_dict = request.model_dump()
    key = _fixture_key("classifier", req_dict)

    t0 = time.monotonic()
    try:
        raw = _load_fixture(fixture_dir, key)
    except FixtureMissingError:
        await _write_ai_call_audit(
            session,
            run_id=run_id,
            entity_id=None,
            ai_role="CLASSIFIER",
            provider="FIXTURE",
            model=None,
            prompt_version=None,
            items=len(request.questions),
            input_tokens=None,
            output_tokens=None,
            cost_eur=0.0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            outcome="ERROR",
            fixture=True,
        )
        raise

    latency_ms = int((time.monotonic() - t0) * 1000)
    answers_raw: list[dict[str, Any]] = raw.get("answers", [])

    # Validate each answer
    answers: list[ClassifierAnswer] = []
    for ans in answers_raw:
        try:
            answers.append(ClassifierAnswer.model_validate(ans))
        except (ValidationError, ValueError) as exc:
            await _write_ai_call_audit(
                session,
                run_id=run_id,
                entity_id=None,
                ai_role="CLASSIFIER",
                provider="FIXTURE",
                model=None,
                prompt_version=None,
                items=len(request.questions),
                input_tokens=raw.get("input_tokens"),
                output_tokens=raw.get("output_tokens"),
                cost_eur=float(raw.get("cost_usd", 0.0)) * usd_eur_rate,
                latency_ms=latency_ms,
                outcome="INVALID_OUTPUT",
                fixture=True,
            )
            raise InvalidOutputError(str(exc)) from exc

    await _write_ai_call_audit(
        session,
        run_id=run_id,
        entity_id=None,
        ai_role="CLASSIFIER",
        provider="FIXTURE",
        model=None,
        prompt_version=None,
        items=len(request.questions),
        input_tokens=raw.get("input_tokens"),
        output_tokens=raw.get("output_tokens"),
        cost_eur=float(raw.get("cost_usd", 0.0)) * usd_eur_rate,
        latency_ms=latency_ms,
        outcome="OK",
        fixture=True,
    )
    return answers


async def escalate(
    inp: EscalationInput,
    *,
    session: AsyncSession,
    fixture_mode: str,
    fixture_dir: str,
    run_id: uuid.UUID | None = None,
    daily_budget_eur: float,
    usd_eur_rate: float = 0.92,
) -> EscalationOutput:
    """[``API-63``](/architecture/interfaces.md#llm): escalate one classification.

    Checks the budget guard before calling.  In ``replay`` mode: loads fixture,
    validates, writes one ``AI_CALL`` audit row with role ``ESCALATION``.
    """
    if fixture_mode != "replay":
        raise RuntimeError(f"escalate() only supports fixture_mode='replay'; got {fixture_mode!r}")

    await _check_budget(session, daily_budget_eur)

    req_dict = inp.model_dump()
    key = _fixture_key("escalation", req_dict)

    t0 = time.monotonic()
    try:
        raw = _load_fixture(fixture_dir, key)
    except FixtureMissingError:
        await _write_ai_call_audit(
            session,
            run_id=run_id,
            entity_id=None,
            ai_role="ESCALATION",
            provider="OPENROUTER",
            model=None,
            prompt_version=None,
            items=1,
            input_tokens=None,
            output_tokens=None,
            cost_eur=0.0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            outcome="ERROR",
            fixture=True,
        )
        raise

    latency_ms = int((time.monotonic() - t0) * 1000)
    try:
        output = EscalationOutput.model_validate(raw.get("output", {}))
    except (ValidationError, ValueError) as exc:
        await _write_ai_call_audit(
            session,
            run_id=run_id,
            entity_id=None,
            ai_role="ESCALATION",
            provider="OPENROUTER",
            model=raw.get("model"),
            prompt_version=raw.get("prompt_version"),
            items=1,
            input_tokens=raw.get("input_tokens"),
            output_tokens=raw.get("output_tokens"),
            cost_eur=float(raw.get("cost_usd", 0.0)) * usd_eur_rate,
            latency_ms=latency_ms,
            outcome="INVALID_OUTPUT",
            fixture=True,
        )
        raise InvalidOutputError(str(exc)) from exc

    await _write_ai_call_audit(
        session,
        run_id=run_id,
        entity_id=None,
        ai_role="ESCALATION",
        provider="OPENROUTER",
        model=raw.get("model"),
        prompt_version=raw.get("prompt_version"),
        items=1,
        input_tokens=raw.get("input_tokens"),
        output_tokens=raw.get("output_tokens"),
        cost_eur=float(raw.get("cost_usd", 0.0)) * usd_eur_rate,
        latency_ms=latency_ms,
        outcome="OK",
        fixture=True,
    )
    return output


async def extract_evidence(
    inp: EvidenceInput,
    *,
    session: AsyncSession,
    fixture_mode: str,
    fixture_dir: str,
    run_id: uuid.UUID | None = None,
    daily_budget_eur: float,
    usd_eur_rate: float = 0.92,
) -> EvidenceOutput:
    """[``API-64``](/architecture/interfaces.md#llm): extract verbatim evidence.

    Checks the budget guard before calling.  In ``replay`` mode: loads fixture,
    validates, writes one ``AI_CALL`` audit row with role ``EVIDENCE``.
    """
    if fixture_mode != "replay":
        raise RuntimeError(
            f"extract_evidence() only supports fixture_mode='replay'; got {fixture_mode!r}"
        )

    await _check_budget(session, daily_budget_eur)

    req_dict = inp.model_dump()
    key = _fixture_key("evidence", req_dict)

    t0 = time.monotonic()
    try:
        raw = _load_fixture(fixture_dir, key)
    except FixtureMissingError:
        await _write_ai_call_audit(
            session,
            run_id=run_id,
            entity_id=None,
            ai_role="EVIDENCE",
            provider="OPENROUTER",
            model=None,
            prompt_version=None,
            items=1,
            input_tokens=None,
            output_tokens=None,
            cost_eur=0.0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            outcome="ERROR",
            fixture=True,
        )
        raise

    latency_ms = int((time.monotonic() - t0) * 1000)
    try:
        output = EvidenceOutput.model_validate(raw.get("output", {}))
    except (ValidationError, ValueError) as exc:
        await _write_ai_call_audit(
            session,
            run_id=run_id,
            entity_id=None,
            ai_role="EVIDENCE",
            provider="OPENROUTER",
            model=raw.get("model"),
            prompt_version=raw.get("prompt_version"),
            items=1,
            input_tokens=raw.get("input_tokens"),
            output_tokens=raw.get("output_tokens"),
            cost_eur=float(raw.get("cost_usd", 0.0)) * usd_eur_rate,
            latency_ms=latency_ms,
            outcome="INVALID_OUTPUT",
            fixture=True,
        )
        raise InvalidOutputError(str(exc)) from exc

    await _write_ai_call_audit(
        session,
        run_id=run_id,
        entity_id=None,
        ai_role="EVIDENCE",
        provider="OPENROUTER",
        model=raw.get("model"),
        prompt_version=raw.get("prompt_version"),
        items=1,
        input_tokens=raw.get("input_tokens"),
        output_tokens=raw.get("output_tokens"),
        cost_eur=float(raw.get("cost_usd", 0.0)) * usd_eur_rate,
        latency_ms=latency_ms,
        outcome="OK",
        fixture=True,
    )
    return output
