"""[Escalation](/architecture/rules.md#escalation): pure function that routes a classification
by ``p_positive`` to POSITIVE, NEGATIVE or ESCALATE.

No I/O.
"""

from __future__ import annotations

from enum import StrEnum

from leadradar.core.enums import FindingStrength


class Route(StrEnum):
    """Decision output of the Escalation rule."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    ESCALATE = "ESCALATE"


def route(
    p_positive: float,
    *,
    escalation_lower: float,
    escalation_upper: float,
) -> Route:
    """Decide whether to accept as positive, reject, or escalate to the LLM.

    Implements [Escalation](/architecture/rules.md#escalation):

    - ``p_positive >= ESCALATION_UPPER`` → ``POSITIVE``
    - ``p_positive <= ESCALATION_LOWER`` → ``NEGATIVE``
    - otherwise → ``ESCALATE``
    """
    if p_positive >= escalation_upper:
        return Route.POSITIVE
    if p_positive <= escalation_lower:
        return Route.NEGATIVE
    return Route.ESCALATE


def post_escalation_route(strength: FindingStrength) -> Route:
    """Convert the LLM escalation's strength into a final route.

    ``NONE`` → ``NEGATIVE``; anything else → ``POSITIVE`` (with finding).
    """
    if strength is FindingStrength.NONE:
        return Route.NEGATIVE
    return Route.POSITIVE
