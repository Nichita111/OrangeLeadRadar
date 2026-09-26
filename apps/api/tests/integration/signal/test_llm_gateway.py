"""Tests of ``API-63`` escalate / ``API-64`` extract_evidence in replay mode.

Covers:
  - In replay, returns the port shape and writes one ``AI_CALL`` row (role ESCALATION/EVIDENCE)
  - A stopped budget yields ``BudgetExhaustedError``
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import FindingStrength
from leadradar.db.models.audit import AuditEvent
from leadradar.worker.ai.gateway import BudgetExhaustedError, escalate, extract_evidence
from leadradar.worker.ai.llm import EscalationInput, EscalationOutput, EvidenceInput, EvidenceOutput
from tests.integration.factories import make_pipeline_run

pytestmark = pytest.mark.integration

FIXTURE_DIR = str(Path(__file__).resolve().parents[2] / "fixtures")
PASSAGE = (
    "Lufthansa Group announced a major cost-reduction programme targeting EUR 500m"
    " in savings through process automation."
)
HEADER = "Lufthansa Group · Annual Report 2026 · 2026-03-06"
QUESTION = {
    "text": "Does the company announce a cost-reduction or operational-efficiency programme?",
    "answer_type": "YES_NO",
    "options": None,
}


@pytest.mark.asyncio
async def test_escalate_replay_returns_escalation_output(
    async_session: AsyncSession,
) -> None:
    """``API-63``: replay returns ``EscalationOutput`` with the correct shape."""
    inp = EscalationInput(
        account_name="Lufthansa Group",
        question=QUESTION,
        passage=PASSAGE,
        language="en",
        header=HEADER,
    )
    out = await escalate(
        inp,
        session=async_session,
        fixture_mode="replay",
        fixture_dir=FIXTURE_DIR,
        run_id=None,
        daily_budget_eur=20.0,
    )
    assert isinstance(out, EscalationOutput)
    assert out.strength in FindingStrength.__members__.values()
    assert 0.0 <= out.confidence <= 1.0


@pytest.mark.asyncio
async def test_escalate_replay_writes_ai_call_audit_row(
    async_session: AsyncSession,
) -> None:
    """``API-63``: each escalate call writes one ``AI_CALL`` audit row with role ESCALATION."""
    run_id = await async_session.run_sync(lambda s: make_pipeline_run(s.connection()))
    inp = EscalationInput(
        account_name="Lufthansa Group",
        question=QUESTION,
        passage=PASSAGE,
        language="en",
        header=HEADER,
    )
    await escalate(
        inp,
        session=async_session,
        fixture_mode="replay",
        fixture_dir=FIXTURE_DIR,
        run_id=run_id,
        daily_budget_eur=20.0,
    )
    await async_session.flush()

    stmt = select(AuditEvent).where(
        AuditEvent.kind == "AI_CALL",
        text("payload->>'ai_role' = 'ESCALATION'"),
    )
    rows = (await async_session.execute(stmt)).scalars().all()
    assert any(
        r.payload.get("ai_role") == "ESCALATION" and r.payload.get("fixture") is True for r in rows
    )


@pytest.mark.asyncio
async def test_extract_evidence_replay_returns_evidence_output(
    async_session: AsyncSession,
) -> None:
    """``API-64``: replay returns ``EvidenceOutput`` with the correct shape."""
    inp = EvidenceInput(
        account_name="Lufthansa Group",
        question=QUESTION,
        passage=PASSAGE,
        language="en",
        header=HEADER,
        strength=FindingStrength.STRONG,
    )
    out = await extract_evidence(
        inp,
        session=async_session,
        fixture_mode="replay",
        fixture_dir=FIXTURE_DIR,
        run_id=None,
        daily_budget_eur=20.0,
    )
    assert isinstance(out, EvidenceOutput)
    assert len(out.quote) >= 20


@pytest.mark.asyncio
async def test_extract_evidence_replay_writes_ai_call_audit_row(
    async_session: AsyncSession,
) -> None:
    """``API-64``: each extract_evidence call writes one ``AI_CALL`` row with role EVIDENCE."""
    run_id = await async_session.run_sync(lambda s: make_pipeline_run(s.connection()))
    inp = EvidenceInput(
        account_name="Lufthansa Group",
        question=QUESTION,
        passage=PASSAGE,
        language="en",
        header=HEADER,
        strength=FindingStrength.STRONG,
    )
    await extract_evidence(
        inp,
        session=async_session,
        fixture_mode="replay",
        fixture_dir=FIXTURE_DIR,
        run_id=run_id,
        daily_budget_eur=20.0,
    )
    await async_session.flush()

    stmt = select(AuditEvent).where(
        AuditEvent.kind == "AI_CALL",
        text("payload->>'ai_role' = 'EVIDENCE'"),
    )
    rows = (await async_session.execute(stmt)).scalars().all()
    assert any(r.payload.get("ai_role") == "EVIDENCE" for r in rows)


@pytest.mark.asyncio
async def test_escalate_budget_exhausted_raises(
    async_session: AsyncSession,
) -> None:
    """A stopped budget (daily_budget_eur=0) yields ``BudgetExhaustedError``."""
    inp = EscalationInput(
        account_name="Lufthansa Group",
        question=QUESTION,
        passage=PASSAGE,
        language="en",
        header=HEADER,
    )
    with pytest.raises(BudgetExhaustedError):
        await escalate(
            inp,
            session=async_session,
            fixture_mode="replay",
            fixture_dir=FIXTURE_DIR,
            run_id=None,
            daily_budget_eur=0.0,
        )


@pytest.mark.asyncio
async def test_extract_evidence_budget_exhausted_raises(
    async_session: AsyncSession,
) -> None:
    """A stopped budget (daily_budget_eur=0) yields ``BudgetExhaustedError``."""
    inp = EvidenceInput(
        account_name="Lufthansa Group",
        question=QUESTION,
        passage=PASSAGE,
        language="en",
        header=HEADER,
        strength=FindingStrength.STRONG,
    )
    with pytest.raises(BudgetExhaustedError):
        await extract_evidence(
            inp,
            session=async_session,
            fixture_mode="replay",
            fixture_dir=FIXTURE_DIR,
            run_id=None,
            daily_budget_eur=0.0,
        )
