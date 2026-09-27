"""Unit tests of [Score breakdown](/architecture/rules.md#score-breakdown)'s
`core.score_breakdown.counted_points`, `FindingView.points`'s source."""

from __future__ import annotations

import uuid

import pytest

from leadradar.core.score_breakdown import counted_points

pytestmark = pytest.mark.unit


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
