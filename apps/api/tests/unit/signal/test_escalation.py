"""Unit tests for [Escalation](/architecture/rules.md#escalation).

Covers:
  - 0.9 → POSITIVE no LLM (>= ESCALATION_UPPER 0.65)
  - 0.5 → ESCALATE (between 0.35 and 0.65)
  - 0.2 → NEGATIVE no LLM (<= ESCALATION_LOWER 0.35)
  - post-escalation NONE → NEGATIVE
  - boundary values exactly at ESCALATION_LOWER / ESCALATION_UPPER
"""

from __future__ import annotations

import pytest

from leadradar.core.enums import FindingStrength
from leadradar.core.signal.escalation import Route, post_escalation_route, route

pytestmark = pytest.mark.unit

LOWER = 0.35
UPPER = 0.65


class TestRoute:
    @pytest.mark.parametrize("p_positive", [0.65, 0.9, 1.0])
    def test_at_or_above_upper_is_positive(self, p_positive: float) -> None:
        assert route(p_positive, escalation_lower=LOWER, escalation_upper=UPPER) is Route.POSITIVE

    @pytest.mark.parametrize("p_positive", [0.35, 0.2, 0.0])
    def test_at_or_below_lower_is_negative(self, p_positive: float) -> None:
        assert route(p_positive, escalation_lower=LOWER, escalation_upper=UPPER) is Route.NEGATIVE

    @pytest.mark.parametrize("p_positive", [0.36, 0.5, 0.64])
    def test_between_boundaries_is_escalate(self, p_positive: float) -> None:
        assert route(p_positive, escalation_lower=LOWER, escalation_upper=UPPER) is Route.ESCALATE

    def test_just_below_upper_is_escalate(self) -> None:
        assert route(0.6499, escalation_lower=LOWER, escalation_upper=UPPER) is Route.ESCALATE

    def test_just_above_lower_is_escalate(self) -> None:
        assert route(0.3501, escalation_lower=LOWER, escalation_upper=UPPER) is Route.ESCALATE


class TestPostEscalationRoute:
    @pytest.mark.parametrize(
        "strength",
        [FindingStrength.WEAK, FindingStrength.MEDIUM, FindingStrength.STRONG],
    )
    def test_non_none_strength_is_positive(self, strength: FindingStrength) -> None:
        assert post_escalation_route(strength) is Route.POSITIVE

    def test_none_strength_is_negative(self) -> None:
        assert post_escalation_route(FindingStrength.NONE) is Route.NEGATIVE
