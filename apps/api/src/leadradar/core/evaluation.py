"""[Evaluation metrics](/architecture/rules.md#evaluation-metrics) (`S-EVL-04`, `AC-49`) and the
label queue's allocation (`S-EVL-03`, `AC-48`): pure functions over rows the caller has already
gathered from the store. No I/O."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leadradar.core.enums import AccountScoreBand, FindingStrength, LeadFeedbackVerdict


class Stratum(StrEnum):
    """The four strata of the [Evaluation metrics](/architecture/rules.md#evaluation-metrics)
    **Label queue**, in the fixed order `label_queue` draws from: a selected passage's
    classification `p_positive` at or below `ESCALATION_LOWER` (`LOW`), inside the band (`BAND`),
    at or above `ESCALATION_UPPER` (`HIGH`); and a passage of a long document that selection did
    not pick for the question (`NOT_SELECTED`)."""

    LOW = "LOW"
    BAND = "BAND"
    HIGH = "HIGH"
    NOT_SELECTED = "NOT_SELECTED"


_STRATA_ORDER: list[Stratum] = list(Stratum)


def label_queue[PairT](strata: Mapping[Stratum, Sequence[PairT]], size: int) -> list[PairT]:
    """Round-robins over the strata in their fixed order, one pair at a time, so each
    contributes as equal a share of `size` as it has pairs; a stratum with fewer pairs than its
    share yields the rest to the others. Each stratum's sequence must already be in the order the
    queue keeps (by the SHA-256 of `<chunk_id>:<question_id>`); this function never reorders it.
    Returns at most `size` pairs, and every pair there is when fewer than `size` exist in all."""
    cursors: dict[Stratum, int] = dict.fromkeys(_STRATA_ORDER, 0)
    result: list[PairT] = []
    while len(result) < size:
        progressed = False
        for stratum in _STRATA_ORDER:
            pairs = strata.get(stratum, ())
            cursor = cursors[stratum]
            if cursor < len(pairs):
                result.append(pairs[cursor])
                cursors[stratum] = cursor + 1
                progressed = True
                if len(result) >= size:
                    break
        if not progressed:
            break
    return result


@dataclass(frozen=True)
class ItemPrediction:
    """One [`evaluation_item`](/architecture/sql-store.md#evaluation_item) replayed through
    [Signal classification](/architecture/rules.md#signal-classification) and
    [Escalation](/architecture/rules.md#escalation) by an `EVALUATION` run. `predictions` passed
    to `evaluation_metrics` must already be ordered by the item's `created_at` then `id`, the
    order its `errors` are listed in ([Evaluation metrics]
    (/architecture/rules.md#evaluation-metrics)): ordering by a timestamp is the store's
    business, not this pure function's."""

    item_id: uuid.UUID
    question_id: uuid.UUID
    question_key: str
    service_id: uuid.UUID
    source_type: str
    expected_strength: FindingStrength
    p_positive: float
    escalated: bool
    final_strength: FindingStrength
    selected: bool


@dataclass(frozen=True)
class EvaluationSettings:
    """The gate and calibration configuration [Evaluation metrics]
    (/architecture/rules.md#evaluation-metrics) needs, already resolved by the caller."""

    eval_min_precision: float
    eval_min_items: int
    eval_classifier_only_p: float
    eval_calibration_bins: int
    eval_max_errors: int


def _is_positive(strength: FindingStrength) -> bool:
    return strength is not FindingStrength.NONE


def _ratio(numerator: float, denominator: int) -> float | None:
    """A ratio whose denominator is zero is null ([Evaluation metrics]
    (/architecture/rules.md#evaluation-metrics))."""
    return None if denominator == 0 else numerator / denominator


@dataclass
class _Confusion:
    items: int = 0
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def precision(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fp)

    def recall(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fn)


def evaluation_metrics(
    predictions: Sequence[ItemPrediction],
    lead_verdicts: Sequence[tuple[AccountScoreBand, LeadFeedbackVerdict]],
    settings: EvaluationSettings,
) -> dict[str, object]:
    """The `metrics` object of [Evaluation metrics](/architecture/rules.md#evaluation-metrics)."""
    items = len(predictions)
    overall = _Confusion()
    tn = 0
    strength_matches = 0
    escalated_count = 0
    classifier_overall = _Confusion()

    per_question: dict[uuid.UUID, tuple[str, uuid.UUID, _Confusion]] = {}
    per_source_type: dict[str, _Confusion] = {}
    missed_evidence_items = 0
    missed_evidence_positive = 0
    bins = settings.eval_calibration_bins
    calibration_counts = [0] * bins
    calibration_sum_p = [0.0] * bins
    calibration_positive = [0] * bins
    errors: list[dict[str, object]] = []

    for prediction in predictions:
        predicted_positive = _is_positive(prediction.final_strength)
        expected_positive = _is_positive(prediction.expected_strength)

        if predicted_positive and expected_positive:
            overall.tp += 1
            if prediction.final_strength == prediction.expected_strength:
                strength_matches += 1
        elif predicted_positive and not expected_positive:
            overall.fp += 1
        elif expected_positive:
            overall.fn += 1
        else:
            tn += 1

        if prediction.escalated:
            escalated_count += 1

        classifier_positive = prediction.p_positive >= settings.eval_classifier_only_p
        if classifier_positive and expected_positive:
            classifier_overall.tp += 1
        elif classifier_positive and not expected_positive:
            classifier_overall.fp += 1
        elif expected_positive:
            classifier_overall.fn += 1

        _, _, question_confusion = per_question.setdefault(
            prediction.question_id, (prediction.question_key, prediction.service_id, _Confusion())
        )
        source_confusion = per_source_type.setdefault(prediction.source_type, _Confusion())
        for confusion in (question_confusion, source_confusion):
            confusion.items += 1
            if predicted_positive and expected_positive:
                confusion.tp += 1
            elif predicted_positive and not expected_positive:
                confusion.fp += 1
            elif expected_positive:
                confusion.fn += 1

        if not prediction.selected:
            missed_evidence_items += 1
            if expected_positive:
                missed_evidence_positive += 1

        bin_index = min(int(prediction.p_positive * bins), bins - 1)
        calibration_counts[bin_index] += 1
        calibration_sum_p[bin_index] += prediction.p_positive
        if expected_positive:
            calibration_positive[bin_index] += 1

        if predicted_positive != expected_positive:
            errors.append(
                {
                    "item_id": str(prediction.item_id),
                    "expected": prediction.expected_strength.value,
                    "predicted": prediction.final_strength.value,
                    "p_positive": prediction.p_positive,
                    "escalated": prediction.escalated,
                }
            )

    per_question_out = {
        str(question_id): {
            "key": key,
            "service_id": str(service_id),
            "items": confusion.items,
            "precision": confusion.precision(),
            "recall": confusion.recall(),
        }
        for question_id, (key, service_id, confusion) in per_question.items()
    }
    per_source_type_out = {
        source_type: {
            "items": confusion.items,
            "precision": confusion.precision(),
            "recall": confusion.recall(),
        }
        for source_type, confusion in per_source_type.items()
    }

    calibration = [
        {
            "count": calibration_counts[index],
            "mean_p": _ratio(calibration_sum_p[index], calibration_counts[index]),
            "positive_rate": _ratio(calibration_positive[index], calibration_counts[index]),
        }
        for index in range(bins)
    ]

    lead_verdict_counts: dict[str, dict[str, int]] = {}
    for band, verdict in lead_verdicts:
        bucket = lead_verdict_counts.setdefault(band.value, {"RELEVANT": 0, "NOT_RELEVANT": 0})
        if verdict is LeadFeedbackVerdict.RELEVANT:
            bucket["RELEVANT"] += 1
        elif verdict is LeadFeedbackVerdict.NOT_RELEVANT:
            bucket["NOT_RELEVANT"] += 1

    return {
        "items": items,
        "tp": overall.tp,
        "fp": overall.fp,
        "tn": tn,
        "fn": overall.fn,
        "precision": overall.precision(),
        "recall": overall.recall(),
        "strength_agreement": _ratio(strength_matches, overall.tp),
        "escalation_rate": _ratio(escalated_count, items),
        "classifier_only": {
            "precision": classifier_overall.precision(),
            "recall": classifier_overall.recall(),
        },
        "per_question": per_question_out,
        "per_source_type": per_source_type_out,
        "missed_evidence": {
            "items": missed_evidence_items,
            "positive_rate": _ratio(missed_evidence_positive, missed_evidence_items),
        },
        "calibration": calibration,
        "errors": errors[: settings.eval_max_errors],
        "lead_verdicts": lead_verdict_counts,
    }


def passed(precision: float | None, items: int, min_precision: float, min_items: int) -> bool:
    """`passed` = `precision >= EVAL_MIN_PRECISION` and `items >= EVAL_MIN_ITEMS`; a null
    precision (nothing predicted positive) is never passing
    ([ADR-14](/architecture/adrs/adr-14-labelled-set-and-precision-gate.md))."""
    return precision is not None and precision >= min_precision and items >= min_items
