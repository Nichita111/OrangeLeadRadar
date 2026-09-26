"""Unit tests for [Evaluation metrics](/architecture/rules.md#evaluation-metrics) and the label
queue's allocation, per "Tests for the coder" of `.work/labelling-and-quality/design.md`."""

from __future__ import annotations

import uuid

import pytest

from leadradar.core.enums import AccountScoreBand, FindingStrength, LeadFeedbackVerdict
from leadradar.core.evaluation import (
    EvaluationSettings,
    ItemPrediction,
    Stratum,
    evaluation_metrics,
    label_queue,
    passed,
)

pytestmark = pytest.mark.unit

_SETTINGS = EvaluationSettings(
    eval_min_precision=0.8,
    eval_min_items=3,
    eval_classifier_only_p=0.5,
    eval_calibration_bins=10,
    eval_max_errors=50,
)


def _prediction(
    *,
    item_id: str = "1",
    question_id: str = "q1",
    question_key: str = "COST_PROGRAM",
    service_id: str = "s1",
    source_type: str = "NEWS",
    expected: FindingStrength = FindingStrength.NONE,
    p_positive: float = 0.5,
    escalated: bool = False,
    final: FindingStrength = FindingStrength.NONE,
    selected: bool = True,
) -> ItemPrediction:
    return ItemPrediction(
        item_id=uuid.UUID(int=int(item_id) if item_id.isdigit() else hash(item_id) & 0xFFFF),
        question_id=uuid.UUID(int=hash(question_id) & 0xFFFF),
        question_key=question_key,
        service_id=uuid.UUID(int=hash(service_id) & 0xFFFF),
        source_type=source_type,
        expected_strength=expected,
        p_positive=p_positive,
        escalated=escalated,
        final_strength=final,
        selected=selected,
    )


class TestLabelQueue:
    def test_takes_an_equal_share_from_each_stratum_when_all_are_full(self) -> None:
        strata = {stratum: [f"{stratum.value}-{i}" for i in range(10)] for stratum in Stratum}
        result = label_queue(strata, size=20)
        assert len(result) == 20
        for stratum in Stratum:
            assert sum(1 for item in result if item.startswith(stratum.value)) == 5

    def test_gives_the_share_of_a_short_stratum_to_the_others(self) -> None:
        strata = {
            Stratum.LOW: ["LOW-0", "LOW-1", "LOW-2"],
            Stratum.BAND: [f"BAND-{i}" for i in range(10)],
            Stratum.HIGH: [f"HIGH-{i}" for i in range(10)],
            Stratum.NOT_SELECTED: [f"NS-{i}" for i in range(10)],
        }
        result = label_queue(strata, size=20)
        assert len(result) == 20
        assert sum(1 for item in result if item.startswith("LOW")) == 3
        # The 17 remaining slots split across the other three strata.
        assert sum(1 for item in result if item.startswith("BAND")) > 3
        assert sum(1 for item in result if item.startswith("HIGH")) > 3

    def test_returns_at_most_the_queue_size_and_everything_when_fewer_pairs_exist(self) -> None:
        strata = {Stratum.LOW: ["a", "b"], Stratum.BAND: ["c"]}
        assert label_queue(strata, size=20) == ["a", "c", "b"]
        assert len(label_queue(strata, size=1)) == 1

    def test_keeps_each_stratums_hash_order(self) -> None:
        strata = {Stratum.LOW: ["z", "a", "m"], Stratum.HIGH: ["y", "b"]}
        result = label_queue(strata, size=5)
        assert [item for item in result if item in ("z", "a", "m")] == ["z", "a", "m"]
        assert [item for item in result if item in ("y", "b")] == ["y", "b"]


class TestPrecisionAndRecall:
    def test_count_a_prediction_positive_when_its_final_strength_is_not_none(self) -> None:
        predictions = [
            _prediction(expected=FindingStrength.WEAK, final=FindingStrength.WEAK),  # tp
            _prediction(expected=FindingStrength.NONE, final=FindingStrength.STRONG),  # fp
            _prediction(expected=FindingStrength.WEAK, final=FindingStrength.NONE),  # fn
            _prediction(expected=FindingStrength.NONE, final=FindingStrength.NONE),  # tn
        ]
        metrics = evaluation_metrics(predictions, [], _SETTINGS)
        assert (metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"]) == (1, 1, 1, 1)

    def test_precision_is_null_when_nothing_is_predicted_positive(self) -> None:
        predictions = [_prediction(expected=FindingStrength.WEAK, final=FindingStrength.NONE)]
        metrics = evaluation_metrics(predictions, [], _SETTINGS)
        assert metrics["precision"] is None

    def test_recall_is_null_when_nothing_is_expected_positive(self) -> None:
        predictions = [_prediction(expected=FindingStrength.NONE, final=FindingStrength.NONE)]
        metrics = evaluation_metrics(predictions, [], _SETTINGS)
        assert metrics["recall"] is None


class TestStrengthAgreement:
    def test_is_the_share_of_true_positives_with_equal_strength(self) -> None:
        predictions = [
            _prediction(expected=FindingStrength.STRONG, final=FindingStrength.STRONG),
            _prediction(expected=FindingStrength.STRONG, final=FindingStrength.WEAK),
        ]
        metrics = evaluation_metrics(predictions, [], _SETTINGS)
        assert metrics["strength_agreement"] == pytest.approx(0.5)

    def test_is_null_without_true_positives(self) -> None:
        predictions = [_prediction(expected=FindingStrength.NONE, final=FindingStrength.NONE)]
        metrics = evaluation_metrics(predictions, [], _SETTINGS)
        assert metrics["strength_agreement"] is None


class TestEscalationRate:
    def test_is_the_share_of_escalated_items(self) -> None:
        predictions = [
            _prediction(escalated=True),
            _prediction(escalated=False),
            _prediction(escalated=False),
            _prediction(escalated=False),
        ]
        metrics = evaluation_metrics(predictions, [], _SETTINGS)
        assert metrics["escalation_rate"] == pytest.approx(0.25)


class TestClassifierOnly:
    def test_is_positive_at_eval_classifier_only_p_and_not_just_below(self) -> None:
        at_threshold = _prediction(p_positive=0.5, expected=FindingStrength.WEAK)
        just_below = _prediction(p_positive=0.4999, expected=FindingStrength.WEAK)
        metrics_at = evaluation_metrics([at_threshold], [], _SETTINGS)
        metrics_below = evaluation_metrics([just_below], [], _SETTINGS)
        classifier_only_at = metrics_at["classifier_only"]
        classifier_only_below = metrics_below["classifier_only"]
        assert isinstance(classifier_only_at, dict)
        assert isinstance(classifier_only_below, dict)
        assert classifier_only_at["recall"] == pytest.approx(1.0)
        assert classifier_only_below["recall"] == pytest.approx(0.0)


class TestPerQuestionAndPerSourceType:
    def test_split_counts_and_ratios(self) -> None:
        service_a = uuid.uuid4()
        service_b = uuid.uuid4()
        service_a_question = uuid.uuid4()
        service_b_question = uuid.uuid4()
        predictions = [
            ItemPrediction(
                item_id=uuid.uuid4(),
                question_id=service_a_question,
                question_key="COST_PROGRAM",
                service_id=service_a,
                source_type="NEWS",
                expected_strength=FindingStrength.WEAK,
                p_positive=0.9,
                escalated=False,
                final_strength=FindingStrength.WEAK,
                selected=True,
            ),
            ItemPrediction(
                item_id=uuid.uuid4(),
                question_id=service_b_question,
                question_key="COST_PROGRAM",  # same key, a different service's question
                service_id=service_b,
                source_type="JOB_POSTING",
                expected_strength=FindingStrength.NONE,
                p_positive=0.9,
                escalated=False,
                final_strength=FindingStrength.WEAK,
                selected=True,
            ),
        ]
        metrics = evaluation_metrics(predictions, [], _SETTINGS)
        per_question = metrics["per_question"]
        per_source_type = metrics["per_source_type"]
        assert isinstance(per_question, dict)
        assert isinstance(per_source_type, dict)
        assert len(per_question) == 2
        assert per_question[str(service_a_question)]["precision"] == pytest.approx(1.0)
        assert per_question[str(service_a_question)]["service_id"] == str(service_a)
        assert per_question[str(service_b_question)]["precision"] == pytest.approx(0.0)
        assert per_question[str(service_b_question)]["service_id"] == str(service_b)
        assert set(per_source_type) == {"NEWS", "JOB_POSTING"}


class TestMissedEvidence:
    def test_counts_only_unselected_items_and_is_null_without_them(self) -> None:
        predictions = [_prediction(selected=True, expected=FindingStrength.WEAK)]
        metrics = evaluation_metrics(predictions, [], _SETTINGS)
        missed = metrics["missed_evidence"]
        assert isinstance(missed, dict)
        assert missed == {"items": 0, "positive_rate": None}

        predictions_with_unselected = [
            _prediction(item_id="1", selected=False, expected=FindingStrength.WEAK),
            _prediction(item_id="2", selected=False, expected=FindingStrength.NONE),
        ]
        metrics2 = evaluation_metrics(predictions_with_unselected, [], _SETTINGS)
        missed2 = metrics2["missed_evidence"]
        assert isinstance(missed2, dict)
        assert missed2 == {"items": 2, "positive_rate": pytest.approx(0.5)}


class TestCalibration:
    def test_uses_equal_width_bins_and_puts_p_one_in_the_last_bin(self) -> None:
        settings = EvaluationSettings(
            eval_min_precision=0.8,
            eval_min_items=1,
            eval_classifier_only_p=0.5,
            eval_calibration_bins=10,
            eval_max_errors=50,
        )
        predictions = [
            _prediction(item_id="1", p_positive=0.0),
            _prediction(item_id="2", p_positive=0.09),
            _prediction(item_id="3", p_positive=0.5),
            _prediction(item_id="4", p_positive=1.0),
        ]
        metrics = evaluation_metrics(predictions, [], settings)
        calibration = metrics["calibration"]
        assert isinstance(calibration, list)
        assert len(calibration) == 10
        assert calibration[0]["count"] == 2  # 0.0 and 0.09 both fall in [0, 0.1)
        assert calibration[5]["count"] == 1  # 0.5 falls in [0.5, 0.6)
        assert calibration[9]["count"] == 1  # a p_positive of 1 falls in the last bin
        assert calibration[1]["count"] == 0
        assert calibration[1]["mean_p"] is None
        assert calibration[1]["positive_rate"] is None


class TestErrors:
    def test_lists_only_misclassified_items_up_to_eval_max_errors_in_order(self) -> None:
        settings = EvaluationSettings(
            eval_min_precision=0.8,
            eval_min_items=1,
            eval_classifier_only_p=0.5,
            eval_calibration_bins=10,
            eval_max_errors=1,
        )
        predictions = [
            _prediction(item_id="1", expected=FindingStrength.WEAK, final=FindingStrength.NONE),
            _prediction(item_id="2", expected=FindingStrength.NONE, final=FindingStrength.STRONG),
            _prediction(item_id="3", expected=FindingStrength.WEAK, final=FindingStrength.WEAK),
        ]
        metrics = evaluation_metrics(predictions, [], settings)
        errors = metrics["errors"]
        assert isinstance(errors, list)
        assert len(errors) == 1
        assert errors[0]["expected"] == "WEAK"
        assert errors[0]["predicted"] == "NONE"


class TestLeadVerdicts:
    def test_counts_in_force_relevant_and_not_relevant_per_current_band(self) -> None:
        lead_verdicts = [
            (AccountScoreBand.HOT, LeadFeedbackVerdict.RELEVANT),
            (AccountScoreBand.HOT, LeadFeedbackVerdict.RELEVANT),
            (AccountScoreBand.HOT, LeadFeedbackVerdict.NOT_RELEVANT),
            (AccountScoreBand.WARM, LeadFeedbackVerdict.NOT_RELEVANT),
        ]
        metrics = evaluation_metrics([], lead_verdicts, _SETTINGS)
        lead_verdicts_out = metrics["lead_verdicts"]
        assert lead_verdicts_out == {
            "HOT": {"RELEVANT": 2, "NOT_RELEVANT": 1},
            "WARM": {"RELEVANT": 0, "NOT_RELEVANT": 1},
        }


class TestPassed:
    def test_passed_exactly_when_precision_at_least_min_and_items_at_least_min(self) -> None:
        assert passed(0.8, 3, min_precision=0.8, min_items=3) is True
        assert passed(0.79, 3, min_precision=0.8, min_items=3) is False
        assert passed(0.8, 2, min_precision=0.8, min_items=3) is False
        assert passed(None, 3, min_precision=0.8, min_items=3) is False
