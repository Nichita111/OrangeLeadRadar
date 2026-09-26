"""[Intent score](/architecture/rules.md#intent-score): `intent(...)`.

Pure function; no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast

from leadradar.core.scoring.decay import decay


@dataclass(frozen=True)
class IntentQuestionResult:
    """Per-question breakdown entry for Intent."""

    question_key: str
    polarity: str  # POSITIVE | NEGATIVE
    weight: str  # HIGH | MEDIUM | LOW | NONE
    weight_value: float
    finding_id: str | None  # the best finding's id, or None when no in-force finding
    strength: str | None  # the best finding's strength, or None
    decay_factor: float  # 0.0 when no finding
    value: float  # strength_value × decay_factor
    points: float  # ± 100 × w_q·c_q / (intent_saturation × M)


@dataclass(frozen=True)
class IntentResult:
    """Output of `intent()`."""

    value: int  # 0–100, half-up rounded
    positive_sum: float  # P
    negative_sum: float  # N
    max_positive: float  # M
    questions: list[IntentQuestionResult]


def intent(
    findings: list[dict[str, object]],
    question_settings: list[dict[str, object]],
    weight_values: dict[str, float],
    strength_values: dict[str, float],
    negative_factor: float,
    intent_saturation: float,
    default_half_life_days: dict[str, int],
    min_decay: float,
    as_of: datetime,
) -> IntentResult:
    """Compute the Intent score.

    `findings` is a flat list of dicts with keys: `id`, `question_key`, `strength`,
    `observed_at` (datetime), `source_type`, `half_life_days` (int|None), `polarity`.
    `question_settings` is a list of dicts with keys: `question_key`, `weight`, `polarity`,
    `half_life_days` (int|None).

    Taking the maximum, not the sum, over a question's findings: the same story told
    by twenty outlets counts once.
    """
    question_results: list[IntentQuestionResult] = []

    m_sum = 0.0  # Σ w_q over positive questions

    for qs in question_settings:
        q_key = str(qs["question_key"])
        weight_level = str(qs["weight"])
        polarity = str(qs["polarity"])
        w = weight_values.get(weight_level, 0.0)
        q_half_life: int | None = cast(int | None, qs.get("half_life_days"))

        if polarity == "POSITIVE":
            m_sum += w

        # Find the max decayed strength for this question
        best_c = 0.0
        best_finding_id: str | None = None
        best_strength: str | None = None
        best_decay = 0.0

        for f in findings:
            if str(f["question_key"]) != q_key:
                continue
            strength_label = str(f["strength"])
            sv = strength_values.get(strength_label, 0.0)
            # Use question setting's half_life_days if set; else decay() falls back to
            # default_half_life_days[source_type].  Findings never carry their own half_life_days.
            d = decay(
                observed_at=cast(datetime, f["observed_at"]),
                source_type=str(f["source_type"]),
                half_life_days=q_half_life,
                default_half_life_days=default_half_life_days,
                min_decay=min_decay,
                as_of=as_of,
            )
            c = sv * d
            if c > best_c:
                best_c = c
                best_finding_id = str(f["id"]) if f.get("id") is not None else None
                best_strength = strength_label
                best_decay = d

        question_results.append(
            IntentQuestionResult(
                question_key=q_key,
                polarity=polarity,
                weight=weight_level,
                weight_value=w,
                finding_id=best_finding_id,
                strength=best_strength if best_c > 0.0 else None,
                decay_factor=best_decay if best_c > 0.0 else 0.0,
                value=best_c,
                points=0.0,  # placeholder, filled below
            )
        )

    if m_sum == 0.0:
        # No positive questions — Intent = 0
        return IntentResult(
            value=0,
            positive_sum=0.0,
            negative_sum=0.0,
            max_positive=0.0,
            questions=question_results,
        )

    p_sum = 0.0
    n_sum = 0.0
    for qr in question_results:
        if qr.polarity == "POSITIVE":
            p_sum += qr.weight_value * qr.value
        else:
            n_sum += qr.weight_value * qr.value

    denominator = intent_saturation * m_sum
    raw = 100.0 * (p_sum - negative_factor * n_sum) / denominator
    clamped = max(0.0, min(100.0, raw))
    value = int(clamped + 0.5)

    # Rebuild with computed points
    final_results: list[IntentQuestionResult] = []
    for qr in question_results:
        if qr.polarity == "POSITIVE":
            pts = 100.0 * (qr.weight_value * qr.value) / denominator
        else:
            pts = -100.0 * negative_factor * (qr.weight_value * qr.value) / denominator
        final_results.append(
            IntentQuestionResult(
                question_key=qr.question_key,
                polarity=qr.polarity,
                weight=qr.weight,
                weight_value=qr.weight_value,
                finding_id=qr.finding_id,
                strength=qr.strength,
                decay_factor=qr.decay_factor,
                value=qr.value,
                points=pts,
            )
        )

    return IntentResult(
        value=value,
        positive_sum=p_sum,
        negative_sum=n_sum,
        max_positive=m_sum,
        questions=final_results,
    )
