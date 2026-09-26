"""The `breakdown` of [`account_score`](/architecture/sql-store.md#account_score), as
[Score breakdown](/architecture/rules.md#score-breakdown) shapes it: a pure shape with no
defaults and no validation, plus `counted_points`, which reads `FindingView.points`
(/architecture/interfaces.md#findingview) for one finding out of a stored `breakdown`. Pure, no
I/O: the breakdown itself is read by the capability function."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from leadradar.core.enums import (
    AccountScoreBand,
    AccountScoreStanding,
    FindingStrength,
    SignalQuestionPolarity,
)
from leadradar.core.scoring_settings import IcpCriterionKind, WeightLevel

Match = Literal["MATCH", "MISMATCH", "UNKNOWN"]


class FitCriterionBreakdown(BaseModel):
    """One entry of `fit.criteria`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    kind: IcpCriterionKind
    weight: WeightLevel
    weight_value: float
    attribute: str | None
    match: Match
    credit: float
    points: float


class FitBreakdown(BaseModel):
    """The `fit` object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: int
    criteria: list[FitCriterionBreakdown]


class QuestionBreakdown(BaseModel):
    """One entry of `intent.questions`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_key: str
    polarity: SignalQuestionPolarity
    weight: WeightLevel
    weight_value: float
    finding_id: UUID
    strength: FindingStrength
    decay: float
    value: float
    points: float


class IntentBreakdown(BaseModel):
    """The `intent` object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: int
    positive_sum: float
    negative_sum: float
    max_positive: float
    questions: list[QuestionBreakdown]


class DisqualifierBreakdown(BaseModel):
    """One entry of `disqualifiers`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    matched: bool
    overridden: bool
    override_id: UUID | None
    finding_id: UUID | None


class ScoreBreakdown(BaseModel):
    """The full `breakdown` shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    settings_version: int
    as_of: datetime
    fit: FitBreakdown
    intent: IntentBreakdown
    disqualifiers: list[DisqualifierBreakdown]
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand


def counted_points(breakdown: dict[str, object], finding_id: uuid.UUID) -> float | None:
    """The `points` of the `intent.questions[]` entry whose `finding_id` is `finding_id`, else
    `None` — the finding is not the counted finding of its question, or was never intent-scored."""
    intent = breakdown.get("intent")
    if not isinstance(intent, dict):
        return None
    questions = intent.get("questions")
    if not isinstance(questions, list):
        return None
    target = str(finding_id)
    for entry in questions:
        if isinstance(entry, dict) and entry.get("finding_id") == target:
            points = entry.get("points")
            return float(points) if points is not None else None
    return None
