"""Unit tests of `core.scoring_settings` ([Scoring settings validation]
(/architecture/rules.md#scoring-settings-validation), `S-CFG-03`, `S-CFG-07`)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from leadradar.core.scoring_settings import (
    Disqualifier,
    ICPCriterion,
    QuestionSetting,
    ScoringSettingsDocument,
    WeightLevel,
    add_question,
    default_scoring_settings,
    drop_retired_industries,
    remove_question,
    validate_scoring_settings,
)

pytestmark = pytest.mark.unit


def _valid_document(**overrides: object) -> ScoringSettingsDocument:
    base = default_scoring_settings().model_dump()
    base.update(overrides)
    return ScoringSettingsDocument.model_validate(base)


def _validate(
    document: ScoringSettingsDocument,
    questions: frozenset[str] = frozenset(),
    industries: frozenset[str] = frozenset(),
) -> list[str]:
    return [
        e.field
        for e in validate_scoring_settings(
            document, active_question_keys=questions, active_industry_codes=industries
        )
    ]


# --- default_scoring_settings -------------------------------------------------------------------


def test_default_settings_match_the_scoring_settings_document_defaults() -> None:
    document = default_scoring_settings()
    assert document.fit_weight == 0.4
    assert document.intent_weight == 0.6
    assert document.min_fit == 40
    assert document.hot_threshold == 70
    assert document.warm_threshold == 40
    assert document.weight_values == {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
    assert document.strength_values == {"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0}
    assert document.default_half_life_days == {
        "NEWS": 90,
        "COMPANY_PUBLICATION": 365,
        "JOB_POSTING": 60,
        "COMPANY_PROFILE": 365,
    }
    assert document.min_decay == 0.05
    assert document.negative_factor == 1.0
    assert document.intent_saturation == 0.5
    assert document.unknown_match == 0.5
    assert document.icp_criteria == []
    assert document.questions == []
    assert document.disqualifiers == []


def test_default_settings_pass_validation_with_no_active_questions() -> None:
    assert _validate(default_scoring_settings()) == []


# --- add_question / remove_question -------------------------------------------------------------


def test_add_question_joins_at_weight_medium_with_no_half_life() -> None:
    document = add_question(default_scoring_settings(), "COST_PROGRAM")
    assert document.questions == [
        QuestionSetting(question_key="COST_PROGRAM", weight=WeightLevel.MEDIUM, half_life_days=None)
    ]


def test_add_question_is_a_no_op_when_already_present() -> None:
    once = add_question(default_scoring_settings(), "COST_PROGRAM")
    twice = add_question(once, "COST_PROGRAM")
    assert twice.questions == once.questions


def test_remove_question_drops_only_the_named_question() -> None:
    document = add_question(add_question(default_scoring_settings(), "A"), "B")
    removed = remove_question(document, "A")
    assert [q.question_key for q in removed.questions] == ["B"]


def test_remove_question_is_a_no_op_when_absent() -> None:
    document = default_scoring_settings()
    assert remove_question(document, "MISSING") == document


# --- drop_retired_industries ---------------------------------------------------------------------


def test_drop_retired_industries_narrows_only_industry_criteria() -> None:
    document = _valid_document(
        icp_criteria=[
            {
                "key": "SECTOR",
                "kind": "INDUSTRY",
                "weight": "HIGH",
                "values": ["LOGISTICS", "RETIRED_ONE"],
            },
            {"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "MEDIUM", "min": 100},
        ]
    )
    dropped = drop_retired_industries(document, frozenset({"LOGISTICS"}))
    industry_criterion = next(c for c in dropped.icp_criteria if c.key == "SECTOR")
    other_criterion = next(c for c in dropped.icp_criteria if c.key == "SIZE")
    assert industry_criterion.values == ["LOGISTICS"]
    assert other_criterion.min == 100


# --- validate_scoring_settings: balance and lines -------------------------------------------------


@pytest.mark.parametrize(
    ("fit_weight", "intent_weight", "expect_error"),
    [(0.4, 0.6, False), (0.3, 0.6, True), (-0.1, 1.1, True), (0.0, 1.0, False), (1.0, 0.0, False)],
)
def test_fit_and_intent_weight_must_sum_to_one_in_zero_to_one(
    fit_weight: float, intent_weight: float, expect_error: bool
) -> None:
    document = _valid_document(fit_weight=fit_weight, intent_weight=intent_weight)
    fields = _validate(document)
    assert bool(fields) == expect_error


@pytest.mark.parametrize(
    ("min_fit", "warm", "hot", "expect_error"),
    [
        (40, 40, 70, False),
        (40, 70, 70, True),  # warm must be strictly below hot
        (40, -1, 70, True),
        (40, 40, 101, True),
        (0, 0, 100, False),
    ],
)
def test_thresholds_must_satisfy_warm_below_hot_within_0_100(
    min_fit: int, warm: int, hot: int, expect_error: bool
) -> None:
    document = _valid_document(min_fit=min_fit, warm_threshold=warm, hot_threshold=hot)
    fields = _validate(document)
    assert bool(fields) == expect_error


def test_weight_values_must_have_all_four_levels_non_negative() -> None:
    missing = _valid_document(weight_values={"HIGH": 3, "MEDIUM": 2, "LOW": 1})
    negative = _valid_document(weight_values={"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": -1})
    assert "/weight_values" in _validate(missing)
    assert "/weight_values" in _validate(negative)


@pytest.mark.parametrize(
    ("weak", "medium", "strong", "expect_error"),
    [
        (0.5, 0.75, 1.0, False),
        (0.8, 0.75, 1.0, True),
        (0.5, 0.75, 1.1, True),
        (0.0, 0.75, 1.0, True),
    ],
)
def test_strength_values_must_satisfy_weak_le_medium_le_strong_in_0_1(
    weak: float, medium: float, strong: float, expect_error: bool
) -> None:
    document = _valid_document(strength_values={"WEAK": weak, "MEDIUM": medium, "STRONG": strong})
    assert bool(_validate(document)) == expect_error


def test_default_half_life_days_must_have_all_four_source_types_positive() -> None:
    missing = _valid_document(default_half_life_days={"NEWS": 90})
    zero = _valid_document(
        default_half_life_days={
            "NEWS": 0,
            "COMPANY_PUBLICATION": 365,
            "JOB_POSTING": 60,
            "COMPANY_PROFILE": 365,
        }
    )
    assert "/default_half_life_days" in _validate(missing)
    assert "/default_half_life_days" in _validate(zero)


@pytest.mark.parametrize(
    ("key", "value", "expect_error"),
    [
        ("min_decay", -0.1, True),
        ("min_decay", 1.0, False),
        ("negative_factor", -1, True),
        ("negative_factor", 0, False),
        ("intent_saturation", 0, True),
        ("intent_saturation", 1.0, False),
        ("unknown_match", 1.1, True),
        ("unknown_match", 0.5, False),
    ],
)
def test_scalar_bounds(key: str, value: float, expect_error: bool) -> None:
    document = _valid_document(**{key: value})
    fields = _validate(document)
    assert (f"/{key}" in fields) == expect_error


# --- ICP criteria ---------------------------------------------------------------------------------


def test_industry_criterion_requires_a_non_empty_list_of_active_industry_codes() -> None:
    document = _valid_document(
        icp_criteria=[
            {"key": "SECTOR", "kind": "INDUSTRY", "weight": "HIGH", "values": ["RETIRED"]}
        ]
    )
    assert "/icp_criteria/0/values" in _validate(document, industries=frozenset({"ACTIVE_ONE"}))
    assert "/icp_criteria/0/values" not in _validate(
        _valid_document(
            icp_criteria=[
                {"key": "SECTOR", "kind": "INDUSTRY", "weight": "HIGH", "values": ["ACTIVE_ONE"]}
            ]
        ),
        industries=frozenset({"ACTIVE_ONE"}),
    )


def test_geography_criterion_requires_valid_iso_country_codes() -> None:
    document = _valid_document(
        icp_criteria=[{"key": "REGION", "kind": "GEOGRAPHY", "weight": "MEDIUM", "values": ["ZZ"]}]
    )
    assert "/icp_criteria/0/values" in _validate(document)
    valid = _valid_document(
        icp_criteria=[{"key": "REGION", "kind": "GEOGRAPHY", "weight": "MEDIUM", "values": ["DE"]}]
    )
    assert "/icp_criteria/0/values" not in _validate(valid)


def test_employee_range_requires_min_and_min_at_most_max() -> None:
    no_min = _valid_document(
        icp_criteria=[{"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "LOW"}]
    )
    bad_range = _valid_document(
        icp_criteria=[
            {"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "LOW", "min": 100, "max": 50}
        ]
    )
    good_range = _valid_document(
        icp_criteria=[
            {"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "LOW", "min": 100, "max": 5000}
        ]
    )
    assert any(f.startswith("/icp_criteria/0") for f in _validate(no_min))
    assert any(f.startswith("/icp_criteria/0") for f in _validate(bad_range))
    assert not any(f.startswith("/icp_criteria/0") for f in _validate(good_range))


def test_criterion_keys_must_be_unique() -> None:
    document = _valid_document(
        icp_criteria=[
            {"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "LOW", "min": 1},
            {"key": "SIZE", "kind": "REVENUE_RANGE", "weight": "LOW", "min": 1},
        ]
    )
    assert "/icp_criteria/1/key" in _validate(document)


# --- questions --------------------------------------------------------------------------------


def test_questions_must_name_every_active_question_exactly_once() -> None:
    document = _valid_document(questions=[{"question_key": "A", "weight": "MEDIUM"}])
    assert "/questions" in _validate(document, questions=frozenset({"A", "B"}))
    assert "/questions" in _validate(document, questions=frozenset())
    assert "/questions" not in _validate(document, questions=frozenset({"A"}))


def test_duplicate_question_keys_are_rejected() -> None:
    document = _valid_document(
        questions=[
            {"question_key": "A", "weight": "MEDIUM"},
            {"question_key": "A", "weight": "LOW"},
        ]
    )
    assert "/questions" in _validate(document, questions=frozenset({"A"}))


# --- disqualifiers ----------------------------------------------------------------------------


def test_icp_mismatch_disqualifier_must_name_an_existing_criterion() -> None:
    document = _valid_document(
        icp_criteria=[{"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "LOW", "min": 1}],
        disqualifiers=[
            {
                "key": "TOO_SMALL",
                "label": "Too small",
                "kind": "ICP_MISMATCH",
                "criterion_key": "MISSING",
            }
        ],
    )
    assert "/disqualifiers/0/criterion_key" in _validate(document)


def test_signal_disqualifier_must_name_an_existing_question_with_a_min_strength() -> None:
    document = _valid_document(
        questions=[{"question_key": "INSOLVENT", "weight": "MEDIUM"}],
        disqualifiers=[
            {
                "key": "BROKE",
                "label": "Insolvent",
                "kind": "SIGNAL",
                "question_key": "MISSING",
                "min_strength": "WEAK",
            }
        ],
    )
    fields = _validate(document, questions=frozenset({"INSOLVENT"}))
    assert "/disqualifiers/0/question_key" in fields

    no_strength = _valid_document(
        questions=[{"question_key": "INSOLVENT", "weight": "MEDIUM"}],
        disqualifiers=[
            {"key": "BROKE", "label": "Insolvent", "kind": "SIGNAL", "question_key": "INSOLVENT"}
        ],
    )
    fields = _validate(no_strength, questions=frozenset({"INSOLVENT"}))
    assert "/disqualifiers/0/min_strength" in fields

    valid = _valid_document(
        questions=[{"question_key": "INSOLVENT", "weight": "MEDIUM"}],
        disqualifiers=[
            {
                "key": "BROKE",
                "label": "Insolvent",
                "kind": "SIGNAL",
                "question_key": "INSOLVENT",
                "min_strength": "WEAK",
            }
        ],
    )
    assert _validate(valid, questions=frozenset({"INSOLVENT"})) == []


def test_disqualifier_keys_must_be_unique() -> None:
    document = _valid_document(
        icp_criteria=[{"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "LOW", "min": 1}],
        disqualifiers=[
            {"key": "SAME", "label": "A", "kind": "ICP_MISMATCH", "criterion_key": "SIZE"},
            {"key": "SAME", "label": "B", "kind": "ICP_MISMATCH", "criterion_key": "SIZE"},
        ],
    )
    assert "/disqualifiers/1/key" in _validate(document)


# --- shapes -------------------------------------------------------------------------------------


def test_icp_criterion_and_question_setting_and_disqualifier_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ICPCriterion.model_validate(
            {"key": "A", "kind": "EMPLOYEE_RANGE", "weight": "LOW", "unknown": 1}
        )
    with pytest.raises(ValidationError):
        QuestionSetting.model_validate({"question_key": "A", "weight": "MEDIUM", "unknown": 1})
    with pytest.raises(ValidationError):
        Disqualifier.model_validate(
            {"key": "A", "label": "A", "kind": "ICP_MISMATCH", "unknown": 1}
        )
