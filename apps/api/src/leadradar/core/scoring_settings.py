"""The [scoring settings document](/architecture/sql-store.md#scoring-settings-document): the
`settings` column of [`scoring_config`](/architecture/sql-store.md#scoring_config). A pure shape
with no defaults and no validation;
[Scoring settings validation](/architecture/rules.md#scoring-settings-validation) is a scoring
feature, not this module."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from leadradar.core.enums import DocumentSourceType, FindingStrength

WeightLevel = Literal["HIGH", "MEDIUM", "LOW", "NONE"]
"""Weight levels of the scoring settings document; not a SQL store enum column."""

IcpCriterionKind = Literal[
    "INDUSTRY", "GEOGRAPHY", "EMPLOYEE_RANGE", "REVENUE_RANGE", "OPERATIONAL_COMPLEXITY"
]

DisqualifierKind = Literal["ICP_MISMATCH", "SIGNAL"]


class IcpCriterion(BaseModel):
    """One entry of `icp_criteria`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    kind: IcpCriterionKind
    weight: WeightLevel
    values: list[str] | None = None
    min: int | None = None
    max: int | None = None


class QuestionSetting(BaseModel):
    """One entry of `questions`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_key: str
    weight: WeightLevel
    half_life_days: int | None = None


class Disqualifier(BaseModel):
    """One entry of `disqualifiers`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    kind: DisqualifierKind
    criterion_key: str | None = None
    question_key: str | None = None
    min_strength: FindingStrength | None = None


class ScoringSettingsDocument(BaseModel):
    """The document itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_weight: float
    intent_weight: float
    min_fit: int
    hot_threshold: int
    warm_threshold: int
    weight_values: dict[WeightLevel, float]
    strength_values: dict[Literal["WEAK", "MEDIUM", "STRONG"], float]
    default_half_life_days: dict[DocumentSourceType, int]
    min_decay: float
    negative_factor: float
    intent_saturation: float
    unknown_match: float
    icp_criteria: list[IcpCriterion]
    questions: list[QuestionSetting]
    disqualifiers: list[Disqualifier]
