"""The `breakdown` of [`account_score`](/architecture/sql-store.md#account_score), as
[Score breakdown](/architecture/rules.md#score-breakdown) shapes it. A pure shape with no
defaults and no validation."""

from __future__ import annotations

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
