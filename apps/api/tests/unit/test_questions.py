"""Unit tests of `core.questions.validate_question_shape` (`S-CFG-02`, `FR-023`)."""

from __future__ import annotations

import pytest

from leadradar.core.enums import SignalQuestionAnswerType
from leadradar.core.questions import validate_question_shape

pytestmark = pytest.mark.unit

YES_NO = SignalQuestionAnswerType.YES_NO
SCALE = SignalQuestionAnswerType.SCALE
CHOICE = SignalQuestionAnswerType.CHOICE

_VALID_OPTIONS: list[dict[str, object]] = [
    {"key": "STRONG", "label": "Strong", "strength": "STRONG"},
    {"key": "NONE", "label": "None", "strength": "NONE"},
]


@pytest.mark.parametrize("answer_type", [YES_NO, SCALE])
def test_non_choice_answer_types_take_no_options(answer_type: SignalQuestionAnswerType) -> None:
    assert validate_question_shape(answer_type, None) == []


@pytest.mark.parametrize("answer_type", [YES_NO, SCALE])
def test_non_choice_answer_types_refuse_options(answer_type: SignalQuestionAnswerType) -> None:
    errors = validate_question_shape(answer_type, _VALID_OPTIONS)
    assert [e.field for e in errors] == ["/options"]


def test_choice_without_options_is_refused() -> None:
    errors = validate_question_shape(CHOICE, None)
    assert [e.field for e in errors] == ["/options"]


def test_choice_needs_at_least_two_options() -> None:
    one: list[dict[str, object]] = [{"key": "A", "label": "A", "strength": "NONE"}]
    errors = validate_question_shape(CHOICE, one)
    assert [e.field for e in errors] == ["/options"]


def test_valid_choice_options_pass() -> None:
    assert validate_question_shape(CHOICE, _VALID_OPTIONS) == []


def test_choice_options_need_at_least_one_strength_none() -> None:
    options: list[dict[str, object]] = [
        {"key": "A", "label": "A", "strength": "WEAK"},
        {"key": "B", "label": "B", "strength": "STRONG"},
    ]
    errors = validate_question_shape(CHOICE, options)
    assert any(e.field == "/options" and "NONE" in e.message for e in errors)


def test_choice_option_keys_must_be_unique() -> None:
    options: list[dict[str, object]] = [
        {"key": "A", "label": "A", "strength": "NONE"},
        {"key": "A", "label": "B", "strength": "STRONG"},
    ]
    errors = validate_question_shape(CHOICE, options)
    assert any(e.field == "/options" and "unique" in e.message for e in errors)


def test_choice_option_requires_key_label_and_a_valid_strength() -> None:
    options: list[dict[str, object]] = [
        {"label": "Missing key", "strength": "NONE"},
        {"key": "B", "strength": "STRONG"},
        {"key": "C", "label": "Bad strength", "strength": "EXTREME"},
    ]
    errors = validate_question_shape(CHOICE, options)
    fields = {e.field for e in errors}
    assert "/options/0/key" in fields
    assert "/options/1/label" in fields
    assert "/options/2/strength" in fields
