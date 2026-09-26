"""[Fit score](/architecture/rules.md#fit-score) (`S-SCO-01`, and [Discovery]
(/architecture/rules.md#discovery) `S-DSC-01`'s `fit_estimate`): how well an account's known
attributes match a service's active ICP criteria. A pure function of the criteria and the
account's attributes; no database, no rounding surprises beyond the rule's own `round`."""

from __future__ import annotations

from leadradar.core.enums import AccountOperationalComplexity
from leadradar.core.scoring_settings import ICPCriterion, ICPCriterionKind


def _criterion_value(
    criterion: ICPCriterion,
    *,
    country_code: str | None,
    industry: str | None,
    employee_count: int | None,
    revenue_eur: int | None,
    operational_complexity: AccountOperationalComplexity | None,
) -> str | int | None:
    """The account's attribute a criterion of this kind matches over."""
    if criterion.kind == ICPCriterionKind.INDUSTRY:
        return industry
    if criterion.kind == ICPCriterionKind.GEOGRAPHY:
        return country_code
    if criterion.kind == ICPCriterionKind.EMPLOYEE_RANGE:
        return employee_count
    if criterion.kind == ICPCriterionKind.REVENUE_RANGE:
        return revenue_eur
    return operational_complexity.value if operational_complexity is not None else None


def _matches(criterion: ICPCriterion, value: str | int) -> bool:
    """Whether `value` matches `criterion`, [Scoring settings document]
    (/architecture/sql-store.md#scoring-settings-document) ICP criterion "Matches when" column.
    Only called once `value` is known (not `None`)."""
    if criterion.kind in (
        ICPCriterionKind.INDUSTRY,
        ICPCriterionKind.GEOGRAPHY,
        ICPCriterionKind.OPERATIONAL_COMPLEXITY,
    ):
        return value in (criterion.values or [])
    assert isinstance(value, int)
    if criterion.min is not None and value < criterion.min:
        return False
    return not (criterion.max is not None and value > criterion.max)


def criterion_match(
    criterion: ICPCriterion,
    *,
    unknown_match: float,
    country_code: str | None,
    industry: str | None,
    employee_count: int | None,
    revenue_eur: int | None,
    operational_complexity: AccountOperationalComplexity | None,
) -> float:
    """`m_c` of [Fit score](/architecture/rules.md#fit-score): 1 when the account's attribute
    matches, 0 when it is known and does not, `unknown_match` when it is unknown."""
    value = _criterion_value(
        criterion,
        country_code=country_code,
        industry=industry,
        employee_count=employee_count,
        revenue_eur=revenue_eur,
        operational_complexity=operational_complexity,
    )
    if value is None:
        return unknown_match
    return 1.0 if _matches(criterion, value) else 0.0


def fit_score(
    criteria: list[ICPCriterion],
    weight_values: dict[str, float],
    unknown_match: float,
    *,
    country_code: str | None,
    industry: str | None,
    employee_count: int | None,
    revenue_eur: int | None,
    operational_complexity: AccountOperationalComplexity | None,
) -> int:
    """[Fit score](/architecture/rules.md#fit-score): `round(100 * sum(w_c * m_c) / sum(w_c))`;
    100 with no criteria or every weight `NONE`, since the service then restricts nothing."""
    total_weight = 0.0
    weighted_match = 0.0
    for criterion in criteria:
        weight = weight_values[criterion.weight.value]
        if weight == 0:
            continue
        total_weight += weight
        weighted_match += weight * criterion_match(
            criterion,
            unknown_match=unknown_match,
            country_code=country_code,
            industry=industry,
            employee_count=employee_count,
            revenue_eur=revenue_eur,
            operational_complexity=operational_complexity,
        )
    if total_weight == 0:
        return 100
    return round(100 * weighted_match / total_weight)
