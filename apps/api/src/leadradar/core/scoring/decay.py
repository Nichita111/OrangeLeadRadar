"""[Recency decay](/architecture/rules.md#recency-decay): `decay(...)`.

Pure function; no I/O.
"""

from __future__ import annotations

from datetime import datetime


def decay(
    observed_at: datetime,
    source_type: str,
    half_life_days: int | None,
    default_half_life_days: dict[str, int],
    min_decay: float,
    as_of: datetime,
) -> float:
    """Return the decay factor for a finding.

    `h` = the question setting's `half_life_days`, else `default_half_life_days[source_type]`.
    `age` = max(0, days between `observed_at` and `as_of`, fractional).
    `factor = 0.5 ^ (age / h)`.  Returns 0.0 when factor < `min_decay`.
    """
    h = half_life_days if half_life_days is not None else default_half_life_days[source_type]
    age_days = max(0.0, (as_of - observed_at).total_seconds() / 86400.0)
    factor = 0.5 ** (age_days / h)
    return 0.0 if factor < min_decay else factor
