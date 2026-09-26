"""[Fit score](/architecture/rules.md#fit-score): `fit(...)`.

Pure function; no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FitCriterionResult:
    """Per-criterion breakdown entry for Fit."""

    key: str
    kind: str
    weight: str
    weight_value: float
    attribute: object  # raw attribute value or None
    match: str  # MATCH | MISMATCH | UNKNOWN
    credit: float  # 0, unknown_match or 1
    points: float  # 100 × w_c·m_c / Σ w_c


@dataclass(frozen=True)
class FitResult:
    """Output of `fit()`."""

    value: int  # 0–100, half-up rounded
    criteria: list[FitCriterionResult]


def fit(
    attributes: dict[str, object],
    icp_criteria: list[dict[str, object]],
    weight_values: dict[str, float],
    unknown_match: float,
) -> FitResult:
    """Compute the Fit score.

    With no criteria, or every weight `NONE`, returns Fit = 100.
    """
    if not icp_criteria:
        return FitResult(value=100, criteria=[])

    results: list[FitCriterionResult] = []
    total_w = 0.0

    for c in icp_criteria:
        key = str(c["key"])
        kind = str(c["kind"])
        weight_level = str(c["weight"])
        w = weight_values.get(weight_level, 0.0)
        total_w += w

    if total_w == 0.0:
        # Every weight is NONE → Fit = 100
        for c in icp_criteria:
            key = str(c["key"])
            kind = str(c["kind"])
            weight_level = str(c["weight"])
            results.append(
                FitCriterionResult(
                    key=key,
                    kind=kind,
                    weight=weight_level,
                    weight_value=0.0,
                    attribute=None,
                    match="UNKNOWN",
                    credit=0.0,
                    points=0.0,
                )
            )
        return FitResult(value=100, criteria=results)

    weighted_sum = 0.0
    for c in icp_criteria:
        key = str(c["key"])
        kind = str(c["kind"])
        weight_level = str(c["weight"])
        w = weight_values.get(weight_level, 0.0)

        attribute_val, match, credit = _criterion_match(c, attributes, unknown_match)
        points = 100.0 * (w * credit) / total_w
        weighted_sum += w * credit

        results.append(
            FitCriterionResult(
                key=key,
                kind=kind,
                weight=weight_level,
                weight_value=w,
                attribute=attribute_val,
                match=match,
                credit=credit,
                points=points,
            )
        )

    raw = 100.0 * weighted_sum / total_w
    # Half-up rounding
    value = int(raw + 0.5)
    return FitResult(value=value, criteria=results)


def _criterion_match(
    c: dict[str, object],
    attributes: dict[str, object],
    unknown_match: float,
) -> tuple[object, str, float]:
    """Return (attribute_value, match_label, credit) for one ICP criterion."""
    kind = str(c["kind"])

    if kind == "INDUSTRY":
        val = attributes.get("industry")
        if val is None:
            return (None, "UNKNOWN", unknown_match)
        raw_values = c.get("values")
        values: list[object] = list(raw_values) if isinstance(raw_values, list) else []
        if str(val) in [str(v) for v in values]:
            return (val, "MATCH", 1.0)
        return (val, "MISMATCH", 0.0)

    if kind == "GEOGRAPHY":
        val = attributes.get("country_code")
        if val is None:
            return (None, "UNKNOWN", unknown_match)
        raw_values = c.get("values")
        values = list(raw_values) if isinstance(raw_values, list) else []
        if str(val) in [str(v) for v in values]:
            return (val, "MATCH", 1.0)
        return (val, "MISMATCH", 0.0)

    if kind == "EMPLOYEE_RANGE":
        val = attributes.get("employee_count")
        if val is None:
            return (None, "UNKNOWN", unknown_match)
        n = float(str(val))
        c_min = c.get("min")
        c_max = c.get("max")
        lo = float(str(c_min)) if c_min is not None else None
        hi = float(str(c_max)) if c_max is not None else None
        if (lo is None or n >= lo) and (hi is None or n <= hi):
            return (val, "MATCH", 1.0)
        return (val, "MISMATCH", 0.0)

    if kind == "REVENUE_RANGE":
        val = attributes.get("revenue_eur")
        if val is None:
            return (None, "UNKNOWN", unknown_match)
        n = float(str(val))
        c_min = c.get("min")
        c_max = c.get("max")
        lo = float(str(c_min)) if c_min is not None else None
        hi = float(str(c_max)) if c_max is not None else None
        if (lo is None or n >= lo) and (hi is None or n <= hi):
            return (val, "MATCH", 1.0)
        return (val, "MISMATCH", 0.0)

    if kind == "OPERATIONAL_COMPLEXITY":
        val = attributes.get("operational_complexity")
        if val is None:
            return (None, "UNKNOWN", unknown_match)
        raw_values = c.get("values")
        values = list(raw_values) if isinstance(raw_values, list) else []
        if str(val) in [str(v) for v in values]:
            return (val, "MATCH", 1.0)
        return (val, "MISMATCH", 0.0)

    # Unknown kind → treat as unknown
    return (None, "UNKNOWN", unknown_match)
