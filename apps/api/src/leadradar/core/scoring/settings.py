"""Pydantic projection of the scoring settings document.

See [scoring settings document](/architecture/sql-store.md#scoring-settings-document).

Read-only: parses the JSONB from `scoring_config.settings`; draft-validation is `S-CFG-03`
and lives in a different task. Defaults match the table's **Default** column exactly.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class IcpCriterion(BaseModel):
    """One ICP criterion in the settings document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    kind: str  # INDUSTRY | GEOGRAPHY | EMPLOYEE_RANGE | REVENUE_RANGE | OPERATIONAL_COMPLEXITY
    weight: str  # HIGH | MEDIUM | LOW | NONE
    values: list[str] | None = None
    min: float | None = None
    max: float | None = None


class QuestionSetting(BaseModel):
    """One question setting in the settings document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_key: str
    weight: str  # HIGH | MEDIUM | LOW | NONE
    half_life_days: int | None = None


class Disqualifier(BaseModel):
    """One disqualifier in the settings document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    kind: str  # ICP_MISMATCH | SIGNAL
    criterion_key: str | None = None
    question_key: str | None = None
    min_strength: str | None = None  # WEAK | MEDIUM | STRONG


class ScoringSettings(BaseModel):
    """Projection of the scoring settings document with defaults from the store spec."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_weight: float = 0.4
    intent_weight: float = 0.6
    min_fit: int = 40
    hot_threshold: int = 70
    warm_threshold: int = 40
    weight_values: dict[str, float] = {
        "HIGH": 3.0,
        "MEDIUM": 2.0,
        "LOW": 1.0,
        "NONE": 0.0,
    }
    strength_values: dict[str, float] = {
        "WEAK": 0.5,
        "MEDIUM": 0.75,
        "STRONG": 1.0,
    }
    default_half_life_days: dict[str, int] = {
        "NEWS": 90,
        "COMPANY_PUBLICATION": 365,
        "JOB_POSTING": 60,
        "COMPANY_PROFILE": 365,
    }
    min_decay: float = 0.05
    negative_factor: float = 1.0
    intent_saturation: float = 0.5
    unknown_match: float = 0.5
    icp_criteria: list[IcpCriterion] = []
    questions: list[QuestionSetting] = []
    disqualifiers: list[Disqualifier] = []
