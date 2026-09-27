"""`API-14` question preview: one passage goes through classification, escalation and evidence
as the pipeline does, and the ranking of the scoring preview (`API-19`)."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest

from leadradar.ai.audit import AiCallContext
from leadradar.ai.gateway import AiGateway
from leadradar.ai.settings import AiGatewaySettings
from leadradar.ai.shapes import ClassifierAnswer, EvidenceOutput
from leadradar.configuration.question_preview import _ask, _Passage, _Question
from leadradar.core.enums import AccountScoreStanding, FindingStrength, SignalQuestionAnswerType
from leadradar.scoring.preview import PreviewScore, _ranks

pytestmark = pytest.mark.unit

_PASSAGE = "Mit dem Programm Fit for Growth senkt der Konzern bis 2026 die Kosten deutlich."


class _Gateway:
    def __init__(self, probabilities: dict[str, float]) -> None:
        self.probabilities = probabilities
        self.evidence_calls = 0

    async def classify(self, request: Any, context: AiCallContext) -> list[ClassifierAnswer]:
        return [
            ClassifierAnswer(question_id=q.id, probabilities=self.probabilities)
            for q in request.questions
        ]

    async def extract_evidence(self, role_input: Any, context: AiCallContext) -> EvidenceOutput:
        self.evidence_calls += 1
        return EvidenceOutput(
            quote="senkt der Konzern bis 2026 die Kosten",
            quote_en="the group cuts costs by 2026",
            rationale="The company announces a cost programme.",
        )


def _question() -> _Question:
    return _Question(
        id="PREVIEW",
        text="Does the company announce a cost-reduction programme?",
        answer_type=SignalQuestionAnswerType.YES_NO,
        options=None,
        source_types=["NEWS"],
        hint_terms=[],
    )


def _passage() -> _Passage:
    return _Passage(_PASSAGE, "the company · 2026-09-27", "de", None, None, None, None)


async def test_a_confident_positive_carries_a_verbatim_quote_and_its_translation() -> None:
    gateway = _Gateway({"YES": 0.9, "NO": 0.1, "STRONG": 0.8, "WEAK": 0.2})
    result = await _ask(
        cast(AiGateway, gateway),
        AiGatewaySettings(),
        _question(),
        _passage(),
        "the company",
        AiCallContext(),
    )
    assert result.strength is FindingStrength.STRONG
    assert result.escalated is False
    assert result.quote is not None and result.quote in _PASSAGE
    assert result.quote_en is not None


async def test_a_confident_negative_asks_no_llm() -> None:
    gateway = _Gateway({"YES": 0.05, "NO": 0.95})
    result = await _ask(
        cast(AiGateway, gateway),
        AiGatewaySettings(),
        _question(),
        _passage(),
        "the company",
        AiCallContext(),
    )
    assert result.strength is FindingStrength.NONE
    assert result.quote is None
    assert gateway.evidence_calls == 0


def test_the_ranking_orders_ranked_accounts_by_priority_intent_fit_then_name() -> None:
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    ranked = AccountScoreStanding.RANKED
    scores = {
        a: PreviewScore(50, 60, 55, ranked, None),
        b: PreviewScore(60, 60, 55, ranked, None),
        c: PreviewScore(90, 90, 90, AccountScoreStanding.DISQUALIFIED, None),
        d: PreviewScore(50, 60, 55, ranked, None),
    }
    ranks = _ranks(scores, {a: "Beta", b: "Gamma", c: "Alpha", d: "Alpha"})
    assert ranks == {b: 1, d: 2, a: 3}
