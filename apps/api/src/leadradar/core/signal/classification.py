"""[Signal classification](/architecture/rules.md#signal-classification): pure functions that
map a classifier's raw answer for one question to ``p_positive`` and a candidate strength.

No I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from leadradar.core.enums import FindingStrength, SignalQuestionAnswerType


@dataclass(frozen=True)
class AnswerMapping:
    """Result of mapping one classifier answer for one question."""

    p_positive: float
    # Candidate strength before escalation; NONE when nothing is positive.
    candidate_strength: FindingStrength
    # CHOICE only: the key of the most probable non-NONE option.
    option_key: str | None


def map_answer(
    *,
    answer_type: SignalQuestionAnswerType,
    probabilities: dict[str, float],
    options: Sequence[Mapping[str, object]] | None = None,
) -> AnswerMapping:
    """Map a classifier's raw answer to ``p_positive`` and candidate strength.

    Implements [Signal classification](/architecture/rules.md#signal-classification).

    Parameters
    ----------
    answer_type:
        The question's ``answer_type``.
    probabilities:
        ``{answer_key: probability}`` from the classifier, as in ``ClassifierAnswer``.
    options:
        For ``CHOICE`` questions, the question's ``options`` list of
        ``{key, label, strength}``.  Required when ``answer_type`` is ``CHOICE``.
    """
    if answer_type is SignalQuestionAnswerType.YES_NO:
        return _map_yes_no(probabilities)
    if answer_type is SignalQuestionAnswerType.SCALE:
        return _map_scale(probabilities)
    if answer_type is SignalQuestionAnswerType.CHOICE:
        if options is None:
            raise ValueError("options required for CHOICE answer type")
        return _map_choice(probabilities, options)
    # Exhaustive — enum has only three values.
    raise ValueError(f"unknown answer_type: {answer_type!r}")  # pragma: no cover


def _map_yes_no(probs: dict[str, float]) -> AnswerMapping:
    """YES_NO: p_positive = P(YES); strength = most probable scale level from the same call.

    Per [Signal classification](/architecture/rules.md#signal-classification): the scale
    sub-question is sent in the same call and its answer carries the strength.  No fallback
    invented here (decision G3).
    """
    p_yes = probs.get("YES", 0.0)
    # The scale question is sent in the same call: keys WEAK, MEDIUM, STRONG.
    best_strength = FindingStrength.NONE
    best_p = 0.0
    for level in (FindingStrength.STRONG, FindingStrength.MEDIUM, FindingStrength.WEAK):
        p = probs.get(level.value, 0.0)
        if p > best_p:
            best_p = p
            best_strength = level
    return AnswerMapping(
        p_positive=p_yes,
        candidate_strength=best_strength,
        option_key=None,
    )


def _map_scale(probs: dict[str, float]) -> AnswerMapping:
    """SCALE: p_positive = 1 − P(NONE); strength = most probable non-NONE level."""
    p_none = probs.get(FindingStrength.NONE.value, 0.0)
    p_positive = 1.0 - p_none
    best_strength = FindingStrength.NONE
    best_p = 0.0
    for level in (FindingStrength.STRONG, FindingStrength.MEDIUM, FindingStrength.WEAK):
        p = probs.get(level.value, 0.0)
        if p > best_p:
            best_p = p
            best_strength = level
    return AnswerMapping(
        p_positive=p_positive,
        candidate_strength=best_strength,
        option_key=None,
    )


def _map_choice(probs: dict[str, float], options: Sequence[Mapping[str, object]]) -> AnswerMapping:
    """CHOICE: p_positive = sum of P(option) for non-NONE options; strength = most probable
    non-NONE option's strength; option_key = that option's key."""
    p_positive = 0.0
    best_p = 0.0
    best_strength = FindingStrength.NONE
    best_key: str | None = None

    for opt in options:
        key = str(opt["key"])
        strength_str = str(opt["strength"])
        if strength_str == FindingStrength.NONE.value:
            continue
        p = probs.get(key, 0.0)
        p_positive += p
        if p > best_p:
            best_p = p
            best_strength = FindingStrength(strength_str)
            best_key = key

    return AnswerMapping(
        p_positive=p_positive,
        candidate_strength=best_strength,
        option_key=best_key,
    )


def observed_at(
    published_at: datetime | None,
    fetched_at: datetime,
) -> datetime:
    """``observed_at`` = ``published_at`` when present, else ``fetched_at``.

    Implements the [finding](/architecture/sql-store.md#finding) ``observed_at`` rule:
    *"The document's ``published_at``, else its ``fetched_at``; copied at creation because
    decay counts from it after the document is purged."*
    """
    return published_at if published_at is not None else fetched_at
