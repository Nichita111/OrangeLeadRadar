"""The [scoring settings document](/architecture/sql-store.md#scoring-settings-document) as one
Pydantic model, the defaults a new service's first draft starts with, the pure transforms a
question or a retired industry applies to it, and [Scoring settings validation]
(/architecture/rules.md#scoring-settings-validation) itself (`S-CFG-03`, `S-CFG-07`).

Pure, no I/O: the capability function (`leadradar.configuration.commands`) supplies the service's
active question keys and the store's active industry codes; this module never reads either.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from leadradar.core.countries import ISO_3166_1_ALPHA_2
from leadradar.core.enums import AccountOperationalComplexity, DocumentSourceType, FindingStrength

# The scoring settings document's Default column
# (/architecture/sql-store.md#scoring-settings-document): the only other place these numbers are
# stated, for a brand new service's first draft.
_DEFAULT_WEIGHT_VALUES: dict[str, float] = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
_DEFAULT_STRENGTH_VALUES: dict[str, float] = {"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0}
_DEFAULT_HALF_LIFE_DAYS: dict[str, int] = {
    "NEWS": 90,
    "COMPANY_PUBLICATION": 365,
    "JOB_POSTING": 60,
    "COMPANY_PROFILE": 365,
}
_DEFAULT_FIT_WEIGHT = 0.4
_DEFAULT_INTENT_WEIGHT = 0.6
_DEFAULT_MIN_FIT = 40
_DEFAULT_HOT_THRESHOLD = 70
_DEFAULT_WARM_THRESHOLD = 40
_DEFAULT_MIN_DECAY = 0.05
_DEFAULT_NEGATIVE_FACTOR = 1.0
_DEFAULT_INTENT_SATURATION = 0.5
_DEFAULT_UNKNOWN_MATCH = 0.5

_MIN_STRENGTH_LEVELS = frozenset(
    {FindingStrength.WEAK, FindingStrength.MEDIUM, FindingStrength.STRONG}
)


class WeightLevel(StrEnum):
    """A weight level of the [scoring settings document]
    (/architecture/sql-store.md#scoring-settings-document): `weight_values`, and the `weight` of
    an ICP criterion or a question setting. `NONE` keeps a question out of Intent while a
    disqualifier still reads it."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class ICPCriterionKind(StrEnum):
    """The `kind` of an ICP criterion of the [scoring settings document]
    (/architecture/sql-store.md#scoring-settings-document)."""

    INDUSTRY = "INDUSTRY"
    GEOGRAPHY = "GEOGRAPHY"
    EMPLOYEE_RANGE = "EMPLOYEE_RANGE"
    REVENUE_RANGE = "REVENUE_RANGE"
    OPERATIONAL_COMPLEXITY = "OPERATIONAL_COMPLEXITY"


class DisqualifierKind(StrEnum):
    """The `kind` of a disqualifier of the [scoring settings document]
    (/architecture/sql-store.md#scoring-settings-document)."""

    ICP_MISMATCH = "ICP_MISMATCH"
    SIGNAL = "SIGNAL"


class ICPCriterion(BaseModel):
    """One entry of `icp_criteria`. Kind-specific operand validity is [Scoring settings
    validation](#validate_scoring_settings), not a type, because it depends on the service's
    active industries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    kind: ICPCriterionKind
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
    """The `settings` column of [`scoring_config`](/architecture/sql-store.md#scoring_config)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fit_weight: float
    intent_weight: float
    min_fit: int
    hot_threshold: int
    warm_threshold: int
    weight_values: dict[str, float]
    strength_values: dict[str, float]
    default_half_life_days: dict[str, int]
    min_decay: float
    negative_factor: float
    intent_saturation: float
    unknown_match: float
    icp_criteria: list[ICPCriterion] = []
    questions: list[QuestionSetting] = []
    disqualifiers: list[Disqualifier] = []


def default_scoring_settings() -> ScoringSettingsDocument:
    """A new service's first draft ([scoring settings document]
    (/architecture/sql-store.md#scoring-settings-document) Default column, `S-CFG-01`): no
    questions, ICP criteria or disqualifiers, since none exist yet."""
    return ScoringSettingsDocument(
        fit_weight=_DEFAULT_FIT_WEIGHT,
        intent_weight=_DEFAULT_INTENT_WEIGHT,
        min_fit=_DEFAULT_MIN_FIT,
        hot_threshold=_DEFAULT_HOT_THRESHOLD,
        warm_threshold=_DEFAULT_WARM_THRESHOLD,
        weight_values=dict(_DEFAULT_WEIGHT_VALUES),
        strength_values=dict(_DEFAULT_STRENGTH_VALUES),
        default_half_life_days=dict(_DEFAULT_HALF_LIFE_DAYS),
        min_decay=_DEFAULT_MIN_DECAY,
        negative_factor=_DEFAULT_NEGATIVE_FACTOR,
        intent_saturation=_DEFAULT_INTENT_SATURATION,
        unknown_match=_DEFAULT_UNKNOWN_MATCH,
    )


def add_question(document: ScoringSettingsDocument, question_key: str) -> ScoringSettingsDocument:
    """`document.questions` with `question_key` joined at weight `MEDIUM`, no half-life
    ([FL-01](/features/service-configuration.md#fl-01-define-a-service-and-its-signal-questions)
    step 2, `API-12`, and `API-13` reactivation). A no-op when it is already there."""
    if any(setting.question_key == question_key for setting in document.questions):
        return document
    joined = QuestionSetting(
        question_key=question_key, weight=WeightLevel.MEDIUM, half_life_days=None
    )
    return document.model_copy(update={"questions": [*document.questions, joined]})


def remove_question(
    document: ScoringSettingsDocument, question_key: str
) -> ScoringSettingsDocument:
    """`document.questions` with `question_key` removed ([FL-01]
    (/features/service-configuration.md#fl-01-define-a-service-and-its-signal-questions) step 4,
    `API-13` deactivation)."""
    kept = [setting for setting in document.questions if setting.question_key != question_key]
    return document.model_copy(update={"questions": kept})


def drop_retired_industries(
    document: ScoringSettingsDocument, active_industry_codes: frozenset[str]
) -> ScoringSettingsDocument:
    """`document.icp_criteria` with every `INDUSTRY` criterion's `values` narrowed to
    `active_industry_codes` ([FL-22]
    (/features/service-configuration.md#fl-22-maintain-industries-and-markets) step 3, "the next
    draft drops a retired industry before it is saved"). Applied only when a draft is freshly
    created from the active version ([Scoring settings validation]
    (/architecture/rules.md#scoring-settings-validation))."""
    criteria = [
        (
            criterion.model_copy(
                update={
                    "values": [v for v in (criterion.values or []) if v in active_industry_codes]
                }
            )
            if criterion.kind == ICPCriterionKind.INDUSTRY
            else criterion
        )
        for criterion in document.icp_criteria
    ]
    return document.model_copy(update={"icp_criteria": criteria})


@dataclass(frozen=True)
class FieldError:
    """One violation of [Scoring settings validation]
    (/architecture/rules.md#scoring-settings-validation) or of [`signal_question`]
    (/architecture/sql-store.md#signal_question) `options` shape: `field` is the JSON pointer of
    the offending key, e.g. `/questions/2/weight`."""

    field: str
    message: str


_WEIGHT_LEVELS = frozenset(level.value for level in WeightLevel)
_SOURCE_TYPES = frozenset(source.value for source in DocumentSourceType)
_OPERATIONAL_COMPLEXITY_VALUES = frozenset(value.value for value in AccountOperationalComplexity)


def _operand_message(kind: ICPCriterionKind) -> str:
    if kind == ICPCriterionKind.INDUSTRY:
        return "values must be a non-empty list of active industry codes."
    if kind == ICPCriterionKind.GEOGRAPHY:
        return "values must be a non-empty list of ISO 3166-1 alpha-2 country codes."
    return "values must be a non-empty list of operational complexity values."


_LIST_OPERAND_KINDS: dict[ICPCriterionKind, frozenset[str] | None] = {
    ICPCriterionKind.GEOGRAPHY: ISO_3166_1_ALPHA_2,
    ICPCriterionKind.OPERATIONAL_COMPLEXITY: _OPERATIONAL_COMPLEXITY_VALUES,
}


def _validate_icp_criteria(
    criteria: list[ICPCriterion], active_industry_codes: frozenset[str]
) -> list[FieldError]:
    errors: list[FieldError] = []
    seen_keys: set[str] = set()
    for index, criterion in enumerate(criteria):
        pointer = f"/icp_criteria/{index}"
        if criterion.key in seen_keys:
            errors.append(FieldError(f"{pointer}/key", "Criterion keys must be unique."))
        seen_keys.add(criterion.key)

        allowed: frozenset[str] | None
        if criterion.kind == ICPCriterionKind.INDUSTRY:
            allowed = active_industry_codes
        else:
            allowed = _LIST_OPERAND_KINDS.get(criterion.kind)

        if allowed is not None:
            if not criterion.values or any(value not in allowed for value in criterion.values):
                errors.append(FieldError(f"{pointer}/values", _operand_message(criterion.kind)))
        else:  # EMPLOYEE_RANGE, REVENUE_RANGE
            if criterion.min is None:
                errors.append(FieldError(f"{pointer}/min", "min is required."))
            elif criterion.max is not None and criterion.min > criterion.max:
                errors.append(FieldError(f"{pointer}/max", "max must be at least min."))
    return errors


def _validate_questions(
    settings: list[QuestionSetting], active_question_keys: frozenset[str]
) -> list[FieldError]:
    present = [setting.question_key for setting in settings]
    errors: list[FieldError] = []
    if len(present) != len(set(present)):
        errors.append(FieldError("/questions", "question_key must be unique."))
    if set(present) != active_question_keys:
        errors.append(
            FieldError(
                "/questions",
                "questions must name every active question of the service exactly once.",
            )
        )
    return errors


def _validate_disqualifiers(
    disqualifiers: list[Disqualifier], document: ScoringSettingsDocument
) -> list[FieldError]:
    errors: list[FieldError] = []
    seen_keys: set[str] = set()
    criterion_keys = {criterion.key for criterion in document.icp_criteria}
    question_keys = {setting.question_key for setting in document.questions}
    for index, disqualifier in enumerate(disqualifiers):
        pointer = f"/disqualifiers/{index}"
        if disqualifier.key in seen_keys:
            errors.append(FieldError(f"{pointer}/key", "Disqualifier keys must be unique."))
        seen_keys.add(disqualifier.key)

        if disqualifier.kind == DisqualifierKind.ICP_MISMATCH:
            if disqualifier.criterion_key not in criterion_keys:
                errors.append(
                    FieldError(
                        f"{pointer}/criterion_key",
                        "criterion_key must name an existing ICP criterion.",
                    )
                )
        else:  # SIGNAL
            if disqualifier.question_key not in question_keys:
                errors.append(
                    FieldError(
                        f"{pointer}/question_key", "question_key must name an existing question."
                    )
                )
            if disqualifier.min_strength not in _MIN_STRENGTH_LEVELS:
                errors.append(
                    FieldError(
                        f"{pointer}/min_strength", "min_strength must be WEAK, MEDIUM or STRONG."
                    )
                )
    return errors


def validate_scoring_settings(
    document: ScoringSettingsDocument,
    *,
    active_question_keys: frozenset[str],
    active_industry_codes: frozenset[str],
) -> list[FieldError]:
    """[Scoring settings validation](/architecture/rules.md#scoring-settings-validation)
    (`S-CFG-03`): every violation of the draft, each with the JSON pointer of the offending key.
    An empty result means the draft may be saved."""
    errors: list[FieldError] = []

    if not (0 <= document.fit_weight <= 1):
        errors.append(FieldError("/fit_weight", "fit_weight must be between 0 and 1."))
    if not (0 <= document.intent_weight <= 1):
        errors.append(FieldError("/intent_weight", "intent_weight must be between 0 and 1."))
    if abs(document.fit_weight + document.intent_weight - 1) > 1e-9:
        errors.append(
            FieldError("/intent_weight", "fit_weight and intent_weight must add up to 1.")
        )

    if not (0 <= document.min_fit <= 100):
        errors.append(FieldError("/min_fit", "min_fit must be between 0 and 100."))
    if not (0 <= document.warm_threshold < document.hot_threshold <= 100):
        errors.append(
            FieldError(
                "/warm_threshold",
                "warm_threshold must be at least 0, below hot_threshold, and hot_threshold at "
                "most 100.",
            )
        )

    if set(document.weight_values) != _WEIGHT_LEVELS or any(
        value < 0 for value in document.weight_values.values()
    ):
        errors.append(
            FieldError(
                "/weight_values", "weight_values must have all four weight levels, non-negative."
            )
        )

    strength_values = document.strength_values
    if {"WEAK", "MEDIUM", "STRONG"} - set(strength_values):
        errors.append(
            FieldError("/strength_values", "strength_values must have WEAK, MEDIUM and STRONG.")
        )
    elif not (
        0 < strength_values["WEAK"] <= strength_values["MEDIUM"] <= strength_values["STRONG"] <= 1
    ):
        errors.append(
            FieldError(
                "/strength_values",
                "strength_values must satisfy WEAK <= MEDIUM <= STRONG, each in (0, 1].",
            )
        )

    if set(document.default_half_life_days) != _SOURCE_TYPES or any(
        value <= 0 for value in document.default_half_life_days.values()
    ):
        errors.append(
            FieldError(
                "/default_half_life_days",
                "default_half_life_days must have all four source types, each greater than 0.",
            )
        )

    if not (0 <= document.min_decay <= 1):
        errors.append(FieldError("/min_decay", "min_decay must be between 0 and 1."))
    if document.negative_factor < 0:
        errors.append(FieldError("/negative_factor", "negative_factor must be at least 0."))
    if not (0 < document.intent_saturation <= 1):
        errors.append(FieldError("/intent_saturation", "intent_saturation must be in (0, 1]."))
    if not (0 <= document.unknown_match <= 1):
        errors.append(FieldError("/unknown_match", "unknown_match must be between 0 and 1."))

    errors.extend(_validate_icp_criteria(document.icp_criteria, active_industry_codes))
    errors.extend(_validate_questions(document.questions, active_question_keys))
    errors.extend(_validate_disqualifiers(document.disqualifiers, document))

    return errors
