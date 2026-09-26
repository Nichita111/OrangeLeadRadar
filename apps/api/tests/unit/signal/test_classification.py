"""Unit tests for [Signal classification](/architecture/rules.md#signal-classification).

Covers:
  - YES_NO: p_positive = P(yes), strength = most probable scale level
  - SCALE: p_positive = 1 − P(NONE), strength = most probable non-NONE level
  - CHOICE: p_positive = Σ P over non-NONE options, option_key = most probable
  - ``observed_at`` = ``published_at`` else ``fetched_at``
  - ``map_answer`` for CHOICE records the matched ``option_key``
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from leadradar.core.enums import FindingStrength, SignalQuestionAnswerType
from leadradar.core.signal.classification import map_answer, observed_at

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)
_PUBLISHED = datetime(2026, 9, 20, 8, 0, 0, tzinfo=UTC)


class TestYesNo:
    def test_p_positive_equals_p_yes(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.YES_NO,
            probabilities={"YES": 0.7, "NO": 0.3, "STRONG": 0.5, "MEDIUM": 0.3, "WEAK": 0.2},
        )
        assert result.p_positive == pytest.approx(0.7)

    def test_strength_is_most_probable_scale_level(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.YES_NO,
            probabilities={"YES": 0.9, "NO": 0.1, "STRONG": 0.6, "MEDIUM": 0.3, "WEAK": 0.1},
        )
        assert result.candidate_strength is FindingStrength.STRONG

    def test_medium_strength_wins(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.YES_NO,
            probabilities={"YES": 0.8, "NO": 0.2, "STRONG": 0.1, "MEDIUM": 0.7, "WEAK": 0.2},
        )
        assert result.candidate_strength is FindingStrength.MEDIUM

    def test_option_key_is_none(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.YES_NO,
            probabilities={"YES": 0.8, "NO": 0.2},
        )
        assert result.option_key is None

    def test_zero_yes_probability(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.YES_NO,
            probabilities={"YES": 0.0, "NO": 1.0},
        )
        assert result.p_positive == pytest.approx(0.0)
        assert result.candidate_strength is FindingStrength.NONE


class TestScale:
    def test_p_positive_is_one_minus_p_none(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.SCALE,
            probabilities={
                "NONE": 0.2,
                "WEAK": 0.3,
                "MEDIUM": 0.3,
                "STRONG": 0.2,
            },
        )
        assert result.p_positive == pytest.approx(0.8)

    def test_strength_is_most_probable_non_none(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.SCALE,
            probabilities={
                "NONE": 0.1,
                "WEAK": 0.1,
                "MEDIUM": 0.2,
                "STRONG": 0.6,
            },
        )
        assert result.candidate_strength is FindingStrength.STRONG

    def test_full_none_gives_zero_p_positive(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.SCALE,
            probabilities={"NONE": 1.0, "WEAK": 0.0, "MEDIUM": 0.0, "STRONG": 0.0},
        )
        assert result.p_positive == pytest.approx(0.0)
        assert result.candidate_strength is FindingStrength.NONE

    def test_option_key_none(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.SCALE,
            probabilities={"NONE": 0.1, "STRONG": 0.9},
        )
        assert result.option_key is None


class TestChoice:
    _OPTIONS = [
        {"key": "SIGNIFICANT_PROGRAM", "label": "Significant programme", "strength": "STRONG"},
        {"key": "MINOR_MENTION", "label": "Minor mention", "strength": "WEAK"},
        {"key": "NOT_APPLICABLE", "label": "Not applicable", "strength": "NONE"},
    ]

    def test_p_positive_sums_non_none_options(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.CHOICE,
            probabilities={
                "SIGNIFICANT_PROGRAM": 0.5,
                "MINOR_MENTION": 0.3,
                "NOT_APPLICABLE": 0.2,
            },
            options=self._OPTIONS,
        )
        assert result.p_positive == pytest.approx(0.8)

    def test_option_key_is_most_probable_non_none(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.CHOICE,
            probabilities={
                "SIGNIFICANT_PROGRAM": 0.6,
                "MINOR_MENTION": 0.2,
                "NOT_APPLICABLE": 0.2,
            },
            options=self._OPTIONS,
        )
        assert result.option_key == "SIGNIFICANT_PROGRAM"
        assert result.candidate_strength is FindingStrength.STRONG

    def test_minor_mention_wins_when_most_probable(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.CHOICE,
            probabilities={
                "SIGNIFICANT_PROGRAM": 0.1,
                "MINOR_MENTION": 0.7,
                "NOT_APPLICABLE": 0.2,
            },
            options=self._OPTIONS,
        )
        assert result.option_key == "MINOR_MENTION"
        assert result.candidate_strength is FindingStrength.WEAK

    def test_only_none_option_selected_gives_zero(self) -> None:
        result = map_answer(
            answer_type=SignalQuestionAnswerType.CHOICE,
            probabilities={
                "SIGNIFICANT_PROGRAM": 0.0,
                "MINOR_MENTION": 0.0,
                "NOT_APPLICABLE": 1.0,
            },
            options=self._OPTIONS,
        )
        assert result.p_positive == pytest.approx(0.0)
        assert result.option_key is None
        assert result.candidate_strength is FindingStrength.NONE

    def test_options_required_raises(self) -> None:
        with pytest.raises(ValueError, match="options required"):
            map_answer(
                answer_type=SignalQuestionAnswerType.CHOICE,
                probabilities={"A": 0.5, "B": 0.5},
                options=None,
            )


class TestObservedAt:
    def test_returns_published_at_when_present(self) -> None:
        result = observed_at(_PUBLISHED, _NOW)
        assert result == _PUBLISHED

    def test_falls_back_to_fetched_at_when_published_none(self) -> None:
        result = observed_at(None, _NOW)
        assert result == _NOW
