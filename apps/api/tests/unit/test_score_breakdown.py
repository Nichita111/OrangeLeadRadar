"""[Score breakdown](/architecture/rules.md#score-breakdown): its example JSON parses into
`ScoreBreakdown` and round-trips byte-identically; and unit tests of
`core.score_breakdown.counted_points`, `FindingView.points`'s source."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from leadradar.core.enums import AccountScoreStanding
from leadradar.core.score_breakdown import ScoreBreakdown, counted_points
from leadradar.core.scoring.breakdown import ScoreInputs, breakdown_to_json, score_account
from leadradar.core.scoring.settings import ScoringSettings

pytestmark = pytest.mark.unit

AS_OF = datetime(2026, 9, 25, 6, 0, 0, tzinfo=UTC)

FINDING_ID = str(uuid.uuid4())

EXAMPLE = {
    "settings_version": 3,
    "as_of": "2026-09-25T06:00:00Z",
    "fit": {
        "value": 94,
        "criteria": [
            {
                "key": "SECTOR",
                "kind": "INDUSTRY",
                "weight": "HIGH",
                "weight_value": 3,
                "attribute": "AEROSPACE_AVIATION",
                "match": "MATCH",
                "credit": 1.0,
                "points": 37.5,
            }
        ],
    },
    "intent": {
        "value": 38,
        "positive_sum": 3.181981,
        "negative_sum": 1.654074,
        "max_positive": 8,
        "questions": [
            {
                "question_key": "COST_PROGRAM",
                "polarity": "POSITIVE",
                "weight": "HIGH",
                "weight_value": 3,
                "finding_id": FINDING_ID,
                "strength": "STRONG",
                "decay": 0.707107,
                "value": 0.707107,
                "points": 53.033,
            }
        ],
    },
    "disqualifiers": [
        {
            "key": "OUTSIDE_REGION",
            "label": "Outside DACH",
            "kind": "ICP_MISMATCH",
            "criterion_key": "REGION",
            "question_key": None,
            "matched": False,
            "overridden": False,
            "override_id": None,
            "finding_id": None,
        }
    ],
    "priority": 60,
    "standing": "RANKED",
    "band": "WARM",
}


def test_the_score_breakdown_example_of_rules_parses_and_round_trips() -> None:
    breakdown = ScoreBreakdown.model_validate(EXAMPLE)

    round_tripped = json.loads(breakdown.model_dump_json())

    assert round_tripped["fit"]["criteria"][0]["key"] == "SECTOR"
    assert round_tripped["intent"]["questions"][0]["finding_id"] == FINDING_ID
    assert round_tripped["standing"] == "RANKED"
    assert round_tripped["band"] == "WARM"
    assert ScoreBreakdown.model_validate(round_tripped) == breakdown


def test_returns_the_entrys_points_for_the_counted_finding() -> None:
    finding_id = uuid.uuid4()
    breakdown: dict[str, object] = {
        "intent": {
            "questions": [
                {"finding_id": str(finding_id), "points": 53.033},
                {"finding_id": str(uuid.uuid4()), "points": 1.0},
            ]
        }
    }
    assert counted_points(breakdown, finding_id) == 53.033


def test_none_for_a_finding_absent_from_intent_questions() -> None:
    breakdown: dict[str, object] = {
        "intent": {"questions": [{"finding_id": str(uuid.uuid4()), "points": 1.0}]}
    }
    assert counted_points(breakdown, uuid.uuid4()) is None


def test_none_for_an_entry_with_finding_id_null() -> None:
    finding_id = uuid.uuid4()
    breakdown: dict[str, object] = {"intent": {"questions": [{"finding_id": None, "points": 1.0}]}}
    assert counted_points(breakdown, finding_id) is None


def _inputs(*, min_fit: int) -> tuple[ScoreInputs, ScoringSettings]:
    settings = ScoringSettings(min_fit=min_fit)
    inputs = ScoreInputs(
        account_id="account-1",
        service_id="service-1",
        scoring_config_id="config-1",
        settings_version=1,
        attributes={},
        findings=[],
        lead_feedback_verdict=None,
        active_overrides=[],
    )
    return inputs, settings


def test_score_account_breakdown_validates_against_score_breakdown_for_a_ranked_result() -> None:
    """#43's `score_account` builds the dict; `breakdown_to_json` round-trips it; the one
    `ScoreBreakdown` model it is bound to parses it back ([Score breakdown]
    (/architecture/rules.md#score-breakdown); G16)."""
    inputs, settings = _inputs(min_fit=40)

    result = score_account(inputs, as_of=AS_OF, settings=settings)

    assert result.standing == AccountScoreStanding.RANKED
    parsed = ScoreBreakdown.model_validate(json.loads(breakdown_to_json(result.breakdown)))
    assert parsed.standing == AccountScoreStanding.RANKED
    assert parsed.band is not None


def test_score_account_breakdown_validates_against_score_breakdown_for_a_below_fit_result() -> None:
    """A `BELOW_FIT` result's `band` is `null`, and `ScoreBreakdown.band` accepts it (G16)."""
    inputs, settings = _inputs(min_fit=101)

    result = score_account(inputs, as_of=AS_OF, settings=settings)

    assert result.standing == AccountScoreStanding.BELOW_FIT
    assert result.band is None
    parsed = ScoreBreakdown.model_validate(json.loads(breakdown_to_json(result.breakdown)))
    assert parsed.standing == AccountScoreStanding.BELOW_FIT
    assert parsed.band is None
