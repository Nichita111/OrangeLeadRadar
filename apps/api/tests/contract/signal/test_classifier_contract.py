"""Contract tests for ``API-62`` classify in ``replay`` fixture mode.

Covers:
  - In replay, returns one ``ClassifierAnswer`` per question with probabilities summing to 1
  - A request with no fixture fails with ``FixtureMissingError``
  - Writes one ``AI_CALL`` audit row with role ``CLASSIFIER``
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.db.models.audit import AuditEvent
from leadradar.worker.ai.classifier import ClassifierQuestion, ClassifierRequest
from leadradar.worker.ai.gateway import FixtureMissingError, classify

pytestmark = pytest.mark.contract

# Shared fixture directory
FIXTURE_DIR = str(Path(__file__).resolve().parents[2] / "fixtures")

# This request matches the hand-authored fixture
_PASSAGE = (
    "Lufthansa Group announced a major cost-reduction programme targeting EUR 500m"
    " in savings through process automation."
)
_CLASSIFIER_REQUEST = ClassifierRequest(
    state=_PASSAGE,
    context="Company: Lufthansa Group (lufthansagroup.com, DE)",
    questions=[
        ClassifierQuestion(
            id="q-cost-001",
            kind="YES_NO",
            text=(
                "About Lufthansa Group: Does the company announce a cost-reduction"
                " or operational-efficiency programme?"
            ),
            options=None,
        ),
        ClassifierQuestion(
            id="q-cost-001__SCALE",
            kind="SCALE",
            text="How strong is the evidence?",
            options=[
                {"key": "WEAK", "label": "Weak"},
                {"key": "MEDIUM", "label": "Medium"},
                {"key": "STRONG", "label": "Strong"},
            ],
        ),
    ],
)


@pytest.mark.asyncio
async def test_classify_replay_returns_answers_with_valid_probabilities(
    async_session: AsyncSession,
) -> None:
    """``API-62``: replay returns one ``ClassifierAnswer`` per question; probs sum to 1."""
    answers = await classify(
        _CLASSIFIER_REQUEST,
        session=async_session,
        fixture_mode="replay",
        fixture_dir=FIXTURE_DIR,
    )
    assert len(answers) == 2
    for ans in answers:
        total = sum(ans.probabilities.values())
        assert abs(total - 1.0) <= 0.001, f"probabilities do not sum to 1: {total}"


@pytest.mark.asyncio
async def test_classify_replay_writes_ai_call_audit_row(
    async_session: AsyncSession,
) -> None:
    """``API-62``: each classify call writes one ``AI_CALL`` audit row with role CLASSIFIER."""
    run_id = uuid.uuid4()
    await classify(
        _CLASSIFIER_REQUEST,
        session=async_session,
        fixture_mode="replay",
        fixture_dir=FIXTURE_DIR,
        run_id=run_id,
    )
    await async_session.flush()

    stmt = select(AuditEvent).where(
        AuditEvent.kind == "AI_CALL",
        text("payload->>'ai_role' = 'CLASSIFIER'"),
    )
    rows = (await async_session.execute(stmt)).scalars().all()
    assert len(rows) >= 1
    row = rows[-1]
    assert row.payload["ai_role"] == "CLASSIFIER"
    assert row.payload["fixture"] is True
    assert row.payload["outcome"] == "OK"


@pytest.mark.asyncio
async def test_classify_replay_missing_fixture_raises(
    async_session: AsyncSession,
) -> None:
    """``API-62``: a request with no fixture fails ``FixtureMissingError``."""
    req = ClassifierRequest(
        state="Some text with no fixture recorded.",
        context=None,
        questions=[
            ClassifierQuestion(
                id="q-no-fixture",
                kind="YES_NO",
                text="No fixture for this.",
                options=None,
            )
        ],
    )
    with pytest.raises(FixtureMissingError):
        await classify(
            req,
            session=async_session,
            fixture_mode="replay",
            fixture_dir=FIXTURE_DIR,
        )
