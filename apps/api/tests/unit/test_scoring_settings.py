"""[Scoring settings document](/architecture/sql-store.md#scoring-settings-document): every
criterion and disqualifier kind parses; an unknown kind is refused."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from leadradar.core.scoring_settings import ScoringSettingsDocument

pytestmark = pytest.mark.unit

DOCUMENT = {
    "fit_weight": 0.4,
    "intent_weight": 0.6,
    "min_fit": 40,
    "hot_threshold": 70,
    "warm_threshold": 40,
    "weight_values": {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0},
    "strength_values": {"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
    "default_half_life_days": {
        "NEWS": 90,
        "COMPANY_PUBLICATION": 365,
        "JOB_POSTING": 60,
        "COMPANY_PROFILE": 365,
    },
    "min_decay": 0.05,
    "negative_factor": 1.0,
    "intent_saturation": 0.5,
    "unknown_match": 0.5,
    "icp_criteria": [
        {"key": "SECTOR", "kind": "INDUSTRY", "weight": "HIGH", "values": ["LOGISTICS_TRANSPORT"]},
        {"key": "REGION", "kind": "GEOGRAPHY", "weight": "MEDIUM", "values": ["DE", "AT", "CH"]},
        {"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "LOW", "min": 100, "max": 10000},
        {"key": "REVENUE", "kind": "REVENUE_RANGE", "weight": "LOW", "min": 1_000_000},
        {
            "key": "COMPLEXITY",
            "kind": "OPERATIONAL_COMPLEXITY",
            "weight": "MEDIUM",
            "values": ["HIGH"],
        },
    ],
    "questions": [{"question_key": "COST_PROGRAM", "weight": "HIGH", "half_life_days": None}],
    "disqualifiers": [
        {
            "key": "OUTSIDE_REGION",
            "label": "Outside DACH",
            "kind": "ICP_MISMATCH",
            "criterion_key": "REGION",
        },
        {
            "key": "ALREADY_CUSTOMER",
            "label": "Already a customer",
            "kind": "SIGNAL",
            "question_key": "IS_CUSTOMER",
            "min_strength": "WEAK",
        },
    ],
}


def test_a_scoring_settings_document_with_every_criterion_and_disqualifier_kind_parses() -> None:
    document = ScoringSettingsDocument.model_validate(DOCUMENT)

    kinds = {criterion.kind for criterion in document.icp_criteria}
    assert kinds == {
        "INDUSTRY",
        "GEOGRAPHY",
        "EMPLOYEE_RANGE",
        "REVENUE_RANGE",
        "OPERATIONAL_COMPLEXITY",
    }
    assert {disqualifier.kind for disqualifier in document.disqualifiers} == {
        "ICP_MISMATCH",
        "SIGNAL",
    }


def test_an_unknown_criterion_kind_is_refused() -> None:
    invalid = {**DOCUMENT, "icp_criteria": [{"key": "X", "kind": "NOT_A_KIND", "weight": "HIGH"}]}

    with pytest.raises(ValidationError):
        ScoringSettingsDocument.model_validate(invalid)
