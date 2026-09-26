"""[Score breakdown](/architecture/rules.md#score-breakdown): its example JSON parses into
`ScoreBreakdown` and round-trips byte-identically; and unit tests of
`core.score_breakdown.counted_points`, `FindingView.points`'s source."""

from __future__ import annotations

import json
import uuid

import pytest

from leadradar.core.score_breakdown import ScoreBreakdown, counted_points

pytestmark = pytest.mark.unit

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
