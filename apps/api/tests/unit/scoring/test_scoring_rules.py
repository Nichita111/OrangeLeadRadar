"""Unit tests for the pure scoring rules.

Covers all design-specified test cases.  No I/O, no database, no sockets.
`AS_OF` = 2026-09-25T06:00:00Z (fixed clock).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from leadradar.core.enums import AccountScoreBand, AccountScoreStanding
from leadradar.core.scoring.alerts import alerts
from leadradar.core.scoring.breakdown import (
    ScoreInputs,
    ScoreResult,
    breakdown_to_json,
    score_account,
)
from leadradar.core.scoring.decay import decay
from leadradar.core.scoring.disqualification import DisqEntry, disqualify
from leadradar.core.scoring.fit import fit
from leadradar.core.scoring.intent import intent
from leadradar.core.scoring.priority import priority_standing_band
from leadradar.core.scoring.rescore import NoChange, WriteNewRow, rescore_decision
from leadradar.core.scoring.settings import ScoringSettings

pytestmark = pytest.mark.unit

AS_OF = datetime(2026, 9, 25, 6, 0, 0, tzinfo=UTC)

# Default settings (from store spec)
_DEFAULT_SETTINGS = ScoringSettings()

# Example 1 ICP criteria (from rules.md Examples)
_EXAMPLE_ICP_CRITERIA: list[dict[str, object]] = [
    {
        "key": "SECTOR",
        "kind": "INDUSTRY",
        "weight": "HIGH",
        "values": ["AEROSPACE_AVIATION", "LOGISTICS_TRANSPORT"],
    },
    {"key": "REGION", "kind": "GEOGRAPHY", "weight": "MEDIUM", "values": ["DE", "AT", "CH"]},
    {"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "LOW", "min": 5000},
    {"key": "COMPLEXITY", "kind": "OPERATIONAL_COMPLEXITY", "weight": "MEDIUM", "values": ["HIGH"]},
]

# Example 1 attributes: industry=AEROSPACE_AVIATION, country=DE, employees=UNKNOWN, complexity=HIGH
_EXAMPLE1_ATTRIBUTES: dict[str, object] = {
    "industry": "AEROSPACE_AVIATION",
    "country_code": "DE",
    "employee_count": None,  # unknown
    "revenue_eur": None,
    "operational_complexity": "HIGH",
}

# Example 2 attributes: same but country=FR
_EXAMPLE2_ATTRIBUTES: dict[str, object] = {
    **_EXAMPLE1_ATTRIBUTES,
    "country_code": "FR",
}

# Example 1 question settings with polarity
_QUESTION_SETTINGS_WITH_POLARITY: list[dict[str, object]] = [
    {
        "question_key": "COST_PROGRAM",
        "weight": "HIGH",
        "half_life_days": None,
        "polarity": "POSITIVE",
    },
    {
        "question_key": "AUTOMATION_HIRING",
        "weight": "MEDIUM",
        "half_life_days": None,
        "polarity": "POSITIVE",
    },
    {
        "question_key": "AI_INITIATIVE",
        "weight": "HIGH",
        "half_life_days": None,
        "polarity": "POSITIVE",
    },
    {
        "question_key": "IN_HOUSE_AUTOMATION",
        "weight": "MEDIUM",
        "half_life_days": None,
        "polarity": "NEGATIVE",
    },
]


def _example1_findings() -> list[dict[str, object]]:
    """Findings for Example 1 (from rules.md Examples)."""
    return [
        {
            "id": "finding-cost-1",
            "question_key": "COST_PROGRAM",
            "strength": "STRONG",
            "observed_at": AS_OF - timedelta(days=45),
            "source_type": "NEWS",
            "half_life_days": None,
        },
        {
            "id": "finding-auto-1",
            "question_key": "AUTOMATION_HIRING",
            "strength": "MEDIUM",
            "observed_at": AS_OF - timedelta(days=30),
            "source_type": "JOB_POSTING",
            "half_life_days": None,
        },
        {
            "id": "finding-inhouse-1",
            "question_key": "IN_HOUSE_AUTOMATION",
            "strength": "STRONG",
            "observed_at": AS_OF - timedelta(days=100),
            "source_type": "COMPANY_PUBLICATION",
            "half_life_days": None,
        },
    ]


def _make_settings_with_examples(
    disqualifiers: list[dict[str, object]] | None = None,
) -> ScoringSettings:
    return ScoringSettings.model_validate(
        {
            "fit_weight": 0.4,
            "intent_weight": 0.6,
            "min_fit": 40,
            "hot_threshold": 70,
            "warm_threshold": 40,
            "weight_values": {"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            "strength_values": {"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
            "default_half_life_days": {
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            "min_decay": 0.05,
            "negative_factor": 1.0,
            "intent_saturation": 0.5,
            "unknown_match": 0.5,
            "icp_criteria": _EXAMPLE_ICP_CRITERIA,
            "questions": [
                {"question_key": "COST_PROGRAM", "weight": "HIGH", "half_life_days": None},
                {"question_key": "AUTOMATION_HIRING", "weight": "MEDIUM", "half_life_days": None},
                {"question_key": "AI_INITIATIVE", "weight": "HIGH", "half_life_days": None},
                {"question_key": "IN_HOUSE_AUTOMATION", "weight": "MEDIUM", "half_life_days": None},
            ],
            "disqualifiers": disqualifiers or [],
        }
    )


class TestDecay:
    def test_90_day_news_finding_45_days_old_decays_to_0_707(self) -> None:
        """90-day NEWS finding 45 days old: 0.5^(45/90) ≈ 0.707107."""
        result = decay(
            observed_at=AS_OF - timedelta(days=45),
            source_type="NEWS",
            half_life_days=None,
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            min_decay=0.05,
            as_of=AS_OF,
        )
        assert abs(result - 0.5 ** (45 / 90)) < 1e-6

    def test_400_day_weak_news_finding_below_min_decay(self) -> None:
        """400-day NEWS finding: 0.5^(400/90) = 0.0459 < 0.05 min_decay → 0.0."""
        result = decay(
            observed_at=AS_OF - timedelta(days=400),
            source_type="NEWS",
            half_life_days=None,
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            min_decay=0.05,
            as_of=AS_OF,
        )
        assert result == 0.0

    def test_future_observed_at_returns_one(self) -> None:
        """A finding in the future gets age=0, decay=1."""
        result = decay(
            observed_at=AS_OF + timedelta(days=10),
            source_type="NEWS",
            half_life_days=None,
            default_half_life_days={"NEWS": 90},
            min_decay=0.05,
            as_of=AS_OF,
        )
        assert result == 1.0


class TestFit:
    def test_example1_fit_is_94(self) -> None:
        """Example 1: Fit = 100 × (3·1 + 2·1 + 1·0.5 + 2·1) / 8 = 93.75 → 94."""
        result = fit(
            attributes=_EXAMPLE1_ATTRIBUTES,
            icp_criteria=_EXAMPLE_ICP_CRITERIA,
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            unknown_match=0.5,
        )
        assert result.value == 94

    def test_example1_size_unknown_credits_unknown_match(self) -> None:
        """SIZE is unknown → credit = unknown_match = 0.5."""
        result = fit(
            attributes=_EXAMPLE1_ATTRIBUTES,
            icp_criteria=_EXAMPLE_ICP_CRITERIA,
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            unknown_match=0.5,
        )
        size_cr = next(c for c in result.criteria if c.key == "SIZE")
        assert size_cr.match == "UNKNOWN"
        assert size_cr.credit == 0.5

    def test_no_criteria_returns_100(self) -> None:
        """No criteria → Fit = 100."""
        result = fit(
            attributes={},
            icp_criteria=[],
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            unknown_match=0.5,
        )
        assert result.value == 100

    def test_all_none_weights_returns_100(self) -> None:
        """Every weight NONE → Fit = 100."""
        result = fit(
            attributes={"industry": "X"},
            icp_criteria=[{"key": "K", "kind": "INDUSTRY", "weight": "NONE", "values": ["X"]}],
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            unknown_match=0.5,
        )
        assert result.value == 100

    def test_example2_region_mismatch_fit_is_69(self) -> None:
        """Example 2: country=FR, REGION mismatch → Fit ≈ 68.75 → 69."""
        result = fit(
            attributes=_EXAMPLE2_ATTRIBUTES,
            icp_criteria=_EXAMPLE_ICP_CRITERIA,
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            unknown_match=0.5,
        )
        assert result.value == 69
        region_cr = next(c for c in result.criteria if c.key == "REGION")
        assert region_cr.match == "MISMATCH"


class TestIntent:
    def test_example1_intent_is_38(self) -> None:
        """Example 1: Intent = 100 × (3.181981 − 1.654074) / (0.5 × 8) ≈ 38.20 → 38."""
        result = intent(
            findings=_example1_findings(),
            question_settings=_QUESTION_SETTINGS_WITH_POLARITY,
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            strength_values={"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
            negative_factor=1.0,
            intent_saturation=0.5,
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            min_decay=0.05,
            as_of=AS_OF,
        )
        assert result.value == 38

    def test_in_house_automation_gives_negative_points(self) -> None:
        """IN_HOUSE_AUTOMATION is NEGATIVE → negative points."""
        result = intent(
            findings=_example1_findings(),
            question_settings=_QUESTION_SETTINGS_WITH_POLARITY,
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            strength_values={"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
            negative_factor=1.0,
            intent_saturation=0.5,
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            min_decay=0.05,
            as_of=AS_OF,
        )
        inhouse_q = next(q for q in result.questions if q.question_key == "IN_HOUSE_AUTOMATION")
        assert inhouse_q.points < 0

    def test_dropping_negative_finding_raises_intent(self) -> None:
        """Dropping IN_HOUSE_AUTOMATION finding raises Intent."""
        findings_without_negative = [
            f for f in _example1_findings() if f["question_key"] != "IN_HOUSE_AUTOMATION"
        ]
        result_with = intent(
            findings=_example1_findings(),
            question_settings=_QUESTION_SETTINGS_WITH_POLARITY,
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            strength_values={"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
            negative_factor=1.0,
            intent_saturation=0.5,
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            min_decay=0.05,
            as_of=AS_OF,
        )
        result_without = intent(
            findings=findings_without_negative,
            question_settings=_QUESTION_SETTINGS_WITH_POLARITY,
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            strength_values={"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
            negative_factor=1.0,
            intent_saturation=0.5,
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            min_decay=0.05,
            as_of=AS_OF,
        )
        assert result_without.value > result_with.value

    def test_no_positive_questions_returns_0(self) -> None:
        """When M=0, Intent=0."""
        all_negative_q = [{**qs, "polarity": "NEGATIVE"} for qs in _QUESTION_SETTINGS_WITH_POLARITY]
        result = intent(
            findings=_example1_findings(),
            question_settings=all_negative_q,
            weight_values={"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
            strength_values={"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
            negative_factor=1.0,
            intent_saturation=0.5,
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            min_decay=0.05,
            as_of=AS_OF,
        )
        assert result.value == 0


class TestPriorityStandingBand:
    def test_example1_priority_60_ranked_warm(self) -> None:
        """Example 1: priority = 0.4×94 + 0.6×38 = 60.4 → 60, RANKED, WARM."""
        priority, standing, band = priority_standing_band(
            fit=94,
            intent=38,
            disq_entries=[],
            lead_feedback_verdict=None,
            fit_weight=0.4,
            intent_weight=0.6,
            min_fit=40,
            hot_threshold=70,
            warm_threshold=40,
        )
        assert priority == 60
        assert standing == AccountScoreStanding.RANKED
        assert band == AccountScoreBand.WARM

    def test_band_boundaries(self) -> None:
        """Priority 70→HOT, 69→WARM, 40→WARM, 39→COLD (all fit=50 so RANKED)."""
        # Use fit=50 (>= min_fit 40) so standing is always RANKED, then force priority via intent
        # priority = fit_weight × fit + intent_weight × intent; use fit_weight=1.0,
        # intent_weight=0.0
        # and inject the exact priority value directly via fit
        for priority_val, expected_band in [
            (70, AccountScoreBand.HOT),
            (69, AccountScoreBand.WARM),
            (40, AccountScoreBand.WARM),
            (39, AccountScoreBand.COLD),
        ]:
            _, s, b = priority_standing_band(
                fit=priority_val,  # fit_weight=1.0, intent_weight=0.0 → priority = fit
                intent=0,
                disq_entries=[],
                lead_feedback_verdict=None,
                fit_weight=1.0,
                intent_weight=0.0,
                min_fit=39,  # allow priority_val=39 to be RANKED
                hot_threshold=70,
                warm_threshold=40,
            )
            assert s == AccountScoreStanding.RANKED, f"expected RANKED for priority {priority_val}"
            assert b == expected_band, f"expected {expected_band} for priority {priority_val}"

    def test_fit_below_min_fit_is_below_fit(self) -> None:
        """Fit 39 < min_fit 40 → BELOW_FIT, no band."""
        _, standing, band = priority_standing_band(
            fit=39,
            intent=50,
            disq_entries=[],
            lead_feedback_verdict=None,
            fit_weight=0.4,
            intent_weight=0.6,
            min_fit=40,
            hot_threshold=70,
            warm_threshold=40,
        )
        assert standing == AccountScoreStanding.BELOW_FIT
        assert band is None

    def test_already_customer_overrides_disqualification(self) -> None:
        """ALREADY_CUSTOMER standing wins even if disqualifier matches."""
        disq_entries = [
            DisqEntry(
                key="K",
                label="L",
                matched=True,
                overridden=False,
                override_id=None,
                finding_id=None,
            )
        ]
        _, standing, band = priority_standing_band(
            fit=50,
            intent=50,
            disq_entries=disq_entries,
            lead_feedback_verdict="ALREADY_CUSTOMER",
            fit_weight=0.4,
            intent_weight=0.6,
            min_fit=40,
            hot_threshold=70,
            warm_threshold=40,
        )
        assert standing == AccountScoreStanding.CUSTOMER

    def test_disqualified_standing_when_excluded(self) -> None:
        """Matched unoverridden disqualifier → DISQUALIFIED."""
        disq_entries = [
            DisqEntry(
                key="K",
                label="L",
                matched=True,
                overridden=False,
                override_id=None,
                finding_id=None,
            )
        ]
        _, standing, band = priority_standing_band(
            fit=50,
            intent=50,
            disq_entries=disq_entries,
            lead_feedback_verdict=None,
            fit_weight=0.4,
            intent_weight=0.6,
            min_fit=40,
            hot_threshold=70,
            warm_threshold=40,
        )
        assert standing == AccountScoreStanding.DISQUALIFIED
        assert band is None


class TestDisqualification:
    def test_example2_excluded_on_outside_region(self) -> None:
        """Example 2 with OUTSIDE_REGION ICP_MISMATCH disqualifier → matched=True."""
        disq_defs = [
            {
                "key": "OUTSIDE_REGION",
                "label": "Outside DACH",
                "kind": "ICP_MISMATCH",
                "criterion_key": "REGION",
            }
        ]
        # Augment attributes with the ICP mismatch flag (done by score_account)
        attrs_with_mismatch = {
            **_EXAMPLE2_ATTRIBUTES,
            "_icp_match_REGION": "MISMATCH",
        }
        entries = disqualify(
            disqualifiers=disq_defs,
            attributes=attrs_with_mismatch,
            findings=[],
            active_overrides=[],
            min_decay=0.05,
            strength_values={"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            as_of=AS_OF,
        )
        assert len(entries) == 1
        assert entries[0].matched is True
        assert entries[0].overridden is False

    def test_example2_with_override_becomes_ranked(self) -> None:
        """Example 2 with ACTIVE override on OUTSIDE_REGION → overridden=True, not excluded."""
        disq_defs = [
            {
                "key": "OUTSIDE_REGION",
                "label": "Outside DACH",
                "kind": "ICP_MISMATCH",
                "criterion_key": "REGION",
            }
        ]
        attrs_with_mismatch = {
            **_EXAMPLE2_ATTRIBUTES,
            "_icp_match_REGION": "MISMATCH",
        }
        overrides = [{"id": "override-1", "rule_key": "OUTSIDE_REGION"}]
        entries = disqualify(
            disqualifiers=disq_defs,
            attributes=attrs_with_mismatch,
            findings=[],
            active_overrides=overrides,
            min_decay=0.05,
            strength_values={"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            as_of=AS_OF,
        )
        assert entries[0].matched is True
        assert entries[0].overridden is True
        assert entries[0].override_id == "override-1"

    def test_signal_disqualifier_below_min_decay_not_matched(self) -> None:
        """A SIGNAL disqualifier with decayed finding (below min_decay) is not matched."""
        disq_defs = [
            {
                "key": "DISQ_STRONG",
                "label": "Strong negative",
                "kind": "SIGNAL",
                "question_key": "IN_HOUSE_AUTOMATION",
                "min_strength": "STRONG",
            }
        ]
        # Need 1578+ days for COMPANY_PUBLICATION (half-life 365 days) to fall below min_decay 0.05.
        # 0.5^(1600/365) ≈ 0.044 < 0.05
        findings = [
            {
                "id": "f1",
                "question_key": "IN_HOUSE_AUTOMATION",
                "strength": "STRONG",
                "observed_at": AS_OF - timedelta(days=1600),
                "source_type": "COMPANY_PUBLICATION",
                "half_life_days": None,
            }
        ]
        entries = disqualify(
            disqualifiers=disq_defs,
            attributes={},
            findings=findings,
            active_overrides=[],
            min_decay=0.05,
            strength_values={"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
            default_half_life_days={
                "NEWS": 90,
                "COMPANY_PUBLICATION": 365,
                "JOB_POSTING": 60,
                "COMPANY_PROFILE": 365,
            },
            as_of=AS_OF,
        )
        assert entries[0].matched is False


class TestScoreBreakdown:
    def _make_inputs_ex1(self) -> ScoreInputs:
        return ScoreInputs(
            account_id="account-1",
            service_id="service-1",
            scoring_config_id="config-1",
            settings_version=1,
            attributes=_EXAMPLE1_ATTRIBUTES,
            findings=_example1_findings(),
            lead_feedback_verdict=None,
            active_overrides=[],
            question_settings_with_polarity=_QUESTION_SETTINGS_WITH_POLARITY,
        )

    def test_example1_full_score(self) -> None:
        """Example 1: fit=94, intent=38, priority=60, standing=RANKED, band=WARM."""
        settings = _make_settings_with_examples()
        inputs = self._make_inputs_ex1()
        result = score_account(inputs, as_of=AS_OF, settings=settings)
        assert result.fit == 94
        assert result.intent == 38
        assert result.priority == 60
        assert result.standing == AccountScoreStanding.RANKED
        assert result.band == AccountScoreBand.WARM

    def test_breakdown_criterion_points_sum_to_fit(self) -> None:
        """Criterion points sum to Fit raw value (before integer rounding)."""
        settings = _make_settings_with_examples()
        inputs = self._make_inputs_ex1()
        result = score_account(inputs, as_of=AS_OF, settings=settings)
        fit_breakdown = cast("dict[str, Any]", result.breakdown["fit"])
        points_sum = sum(c["points"] for c in fit_breakdown["criteria"])
        # points sum should equal the raw Fit × ... but checking the total matches the value
        # approximately (before rounding)
        assert abs(points_sum - 93.75) < 0.001

    def test_breakdown_question_points_sum_to_raw_intent(self) -> None:
        """Question points sum to raw Intent (before rounding/clamping)."""
        settings = _make_settings_with_examples()
        inputs = self._make_inputs_ex1()
        result = score_account(inputs, as_of=AS_OF, settings=settings)
        questions = cast("dict[str, Any]", result.breakdown["intent"])["questions"]
        points_sum = sum(q["points"] for q in questions)
        # raw = 100 × (3.181981 − 1.654074) / (0.5 × 8) ≈ 38.20
        assert abs(points_sum - 38.20) < 0.1

    def test_byte_identical_json_for_same_inputs(self) -> None:
        """Two calls with identical inputs produce byte-identical JSON ([N-04])."""
        settings = _make_settings_with_examples()
        inputs = self._make_inputs_ex1()
        r1 = score_account(inputs, as_of=AS_OF, settings=settings)
        r2 = score_account(inputs, as_of=AS_OF, settings=settings)
        j1 = breakdown_to_json(r1.breakdown)
        j2 = breakdown_to_json(r2.breakdown)
        assert j1 == j2

    def test_sorted_keys_in_json(self) -> None:
        """JSON has sorted keys for deterministic output ([N-04])."""
        settings = _make_settings_with_examples()
        inputs = self._make_inputs_ex1()
        result = score_account(inputs, as_of=AS_OF, settings=settings)
        j = breakdown_to_json(result.breakdown)
        parsed = json.loads(j)
        # Top-level keys must be in sorted order
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_six_decimal_rounding(self) -> None:
        """All numeric values in the breakdown are rounded to 6 decimal places."""
        settings = _make_settings_with_examples()
        inputs = self._make_inputs_ex1()
        result = score_account(inputs, as_of=AS_OF, settings=settings)
        j = breakdown_to_json(result.breakdown)
        parsed = json.loads(j)
        # spot-check: intent positive_sum
        ps = parsed["intent"]["positive_sum"]
        assert ps == round(ps, 6)

    def test_no_classifier_probability_in_score_types(self) -> None:
        """No float from classifier/LLM appears as a score, band, standing or exclusion.

        The ScoreResult has only rule-derived values: fit (int), intent (int), priority (int),
        standing (enum), band (enum|None). [S-SCO-08, AC-40]
        """
        settings = _make_settings_with_examples()
        inputs = self._make_inputs_ex1()
        result = score_account(inputs, as_of=AS_OF, settings=settings)
        # fit, intent, priority are all int
        assert isinstance(result.fit, int)
        assert isinstance(result.intent, int)
        assert isinstance(result.priority, int)
        # standing and band are enums, not floats
        assert isinstance(result.standing, AccountScoreStanding)
        assert result.band is None or isinstance(result.band, AccountScoreBand)

    def test_example2_with_outside_region_disqualifier(self) -> None:
        """Example 2 with OUTSIDE_REGION disqualifier → standing=DISQUALIFIED."""
        settings = _make_settings_with_examples(
            disqualifiers=[
                {
                    "key": "OUTSIDE_REGION",
                    "label": "Outside DACH",
                    "kind": "ICP_MISMATCH",
                    "criterion_key": "REGION",
                }
            ]
        )
        inputs = ScoreInputs(
            account_id="account-2",
            service_id="service-1",
            scoring_config_id="config-1",
            settings_version=1,
            attributes=_EXAMPLE2_ATTRIBUTES,
            findings=_example1_findings(),
            lead_feedback_verdict=None,
            active_overrides=[],
            question_settings_with_polarity=_QUESTION_SETTINGS_WITH_POLARITY,
        )
        result = score_account(inputs, as_of=AS_OF, settings=settings)
        assert result.standing == AccountScoreStanding.DISQUALIFIED
        assert result.band is None

    def test_example2_with_override_becomes_ranked_warm(self) -> None:
        """Example 2 with ACTIVE override on OUTSIDE_REGION → RANKED, WARM."""
        settings = _make_settings_with_examples(
            disqualifiers=[
                {
                    "key": "OUTSIDE_REGION",
                    "label": "Outside DACH",
                    "kind": "ICP_MISMATCH",
                    "criterion_key": "REGION",
                }
            ]
        )
        inputs = ScoreInputs(
            account_id="account-2",
            service_id="service-1",
            scoring_config_id="config-1",
            settings_version=1,
            attributes=_EXAMPLE2_ATTRIBUTES,
            findings=_example1_findings(),
            lead_feedback_verdict=None,
            active_overrides=[{"id": "override-1", "rule_key": "OUTSIDE_REGION"}],
            question_settings_with_polarity=_QUESTION_SETTINGS_WITH_POLARITY,
        )
        result = score_account(inputs, as_of=AS_OF, settings=settings)
        assert result.standing == AccountScoreStanding.RANKED
        assert result.band == AccountScoreBand.WARM


class TestRescoreDecision:
    def _make_score_result(self, **kwargs: Any) -> ScoreResult:
        defaults: dict[str, Any] = {
            "scoring_config_id": "config-1",
            "fit": 94,
            "intent": 38,
            "priority": 60,
            "standing": AccountScoreStanding.RANKED,
            "band": AccountScoreBand.WARM,
            "breakdown": {"settings_version": 1, "as_of": "2026-09-25T06:00:00Z"},
            "finding_ids": frozenset(["f1", "f2"]),
            "override_ids": frozenset(),
        }
        defaults.update(kwargs)
        return ScoreResult(**defaults)

    def test_no_current_row_always_writes(self) -> None:
        """No current row → WriteNewRow."""
        result = self._make_score_result()
        decision = rescore_decision(result, None)
        assert isinstance(decision, WriteNewRow)

    def test_equal_inputs_no_change(self) -> None:
        """Identical score → NoChange."""
        result = self._make_score_result()
        current_row: dict[str, object] = {
            "scoring_config_id": "config-1",
            "fit": 94,
            "intent": 38,
            "priority": 60,
            "standing": "RANKED",
            "band": "WARM",
            "breakdown": {
                "intent": {"questions": [{"finding_id": "f1"}, {"finding_id": "f2"}]},
                "disqualifiers": [],
            },
        }
        decision = rescore_decision(result, current_row)
        assert isinstance(decision, NoChange)

    def test_changed_finding_set_writes_new_row(self) -> None:
        """Different finding ids → WriteNewRow."""
        result = self._make_score_result(finding_ids=frozenset(["f1", "f3"]))
        current_row: dict[str, object] = {
            "scoring_config_id": "config-1",
            "fit": 94,
            "intent": 38,
            "priority": 60,
            "standing": "RANKED",
            "band": "WARM",
            "breakdown": {
                "intent": {"questions": [{"finding_id": "f1"}, {"finding_id": "f2"}]},
                "disqualifiers": [],
            },
        }
        decision = rescore_decision(result, current_row)
        assert isinstance(decision, WriteNewRow)

    def test_changed_config_id_writes_new_row(self) -> None:
        """Different scoring_config_id → WriteNewRow."""
        result = self._make_score_result(scoring_config_id="config-2")
        current_row: dict[str, object] = {
            "scoring_config_id": "config-1",
            "fit": 94,
            "intent": 38,
            "priority": 60,
            "standing": "RANKED",
            "band": "WARM",
            "breakdown": {"intent": {"questions": []}, "disqualifiers": []},
        }
        decision = rescore_decision(result, current_row)
        assert isinstance(decision, WriteNewRow)


class TestAlerts:
    def test_band_up_warm_to_hot(self) -> None:
        """WARM → HOT: new_rank(3) > prev_rank(2) and ≥ 2 → BAND_UP."""
        result = alerts(
            new_score_id="score-1",
            new_standing=AccountScoreStanding.RANKED,
            new_band=AccountScoreBand.HOT,
            previous_band=AccountScoreBand.WARM,
            new_findings=[],
            active_settings={"questions": [], "weight_values": {}},
            alert_max_age_days=14,
            as_of=AS_OF,
            account_id="account-1",
            service_id="service-1",
        )
        from leadradar.core.enums import AlertKind

        assert any(a.kind == AlertKind.BAND_UP for a in result)

    def test_band_down_no_alert(self) -> None:
        """HOT → WARM (rank decrease): no BAND_UP."""
        result = alerts(
            new_score_id="score-1",
            new_standing=AccountScoreStanding.RANKED,
            new_band=AccountScoreBand.WARM,
            previous_band=AccountScoreBand.HOT,
            new_findings=[],
            active_settings={"questions": [], "weight_values": {}},
            alert_max_age_days=14,
            as_of=AS_OF,
            account_id="account-1",
            service_id="service-1",
        )
        from leadradar.core.enums import AlertKind

        assert not any(a.kind == AlertKind.BAND_UP for a in result)

    def test_cold_to_warm_triggers_band_up(self) -> None:
        """None (no band) → WARM: new_rank(2) > prev_rank(0) and ≥ 2 → BAND_UP."""
        result = alerts(
            new_score_id="score-1",
            new_standing=AccountScoreStanding.RANKED,
            new_band=AccountScoreBand.WARM,
            previous_band=None,
            new_findings=[],
            active_settings={"questions": [], "weight_values": {}},
            alert_max_age_days=14,
            as_of=AS_OF,
            account_id="account-1",
            service_id="service-1",
        )
        from leadradar.core.enums import AlertKind

        assert any(a.kind == AlertKind.BAND_UP for a in result)

    def test_strong_signal_creates_alert_for_ranked_account(self) -> None:
        """New STRONG HIGH POSITIVE finding within alert_max_age_days on RANKED → STRONG_SIGNAL."""
        new_finding = {
            "id": "f-new",
            "question_key": "COST_PROGRAM",
            "strength": "STRONG",
            "observed_at": AS_OF - timedelta(days=3),
        }
        active_settings = {
            "questions": [
                {"question_key": "COST_PROGRAM", "weight": "HIGH", "polarity": "POSITIVE"}
            ],
            "weight_values": {"HIGH": 3.0},
        }
        result = alerts(
            new_score_id="score-1",
            new_standing=AccountScoreStanding.RANKED,
            new_band=AccountScoreBand.HOT,
            previous_band=AccountScoreBand.HOT,
            new_findings=[new_finding],
            active_settings=active_settings,
            alert_max_age_days=14,
            as_of=AS_OF,
            account_id="account-1",
            service_id="service-1",
        )
        from leadradar.core.enums import AlertKind

        assert any(a.kind == AlertKind.STRONG_SIGNAL for a in result)

    def test_strong_signal_not_created_for_non_ranked(self) -> None:
        """STRONG SIGNAL on DISQUALIFIED account → no alert."""
        new_finding = {
            "id": "f-new",
            "question_key": "COST_PROGRAM",
            "strength": "STRONG",
            "observed_at": AS_OF - timedelta(days=3),
        }
        active_settings = {
            "questions": [
                {"question_key": "COST_PROGRAM", "weight": "HIGH", "polarity": "POSITIVE"}
            ],
            "weight_values": {"HIGH": 3.0},
        }
        result = alerts(
            new_score_id="score-1",
            new_standing=AccountScoreStanding.DISQUALIFIED,
            new_band=None,
            previous_band=None,
            new_findings=[new_finding],
            active_settings=active_settings,
            alert_max_age_days=14,
            as_of=AS_OF,
            account_id="account-1",
            service_id="service-1",
        )
        from leadradar.core.enums import AlertKind

        assert not any(a.kind == AlertKind.STRONG_SIGNAL for a in result)

    def test_strong_signal_beyond_alert_max_age_days_no_alert(self) -> None:
        """Finding older than alert_max_age_days → no STRONG_SIGNAL."""
        new_finding = {
            "id": "f-old",
            "question_key": "COST_PROGRAM",
            "strength": "STRONG",
            "observed_at": AS_OF - timedelta(days=15),  # > 14 days
        }
        active_settings = {
            "questions": [
                {"question_key": "COST_PROGRAM", "weight": "HIGH", "polarity": "POSITIVE"}
            ],
            "weight_values": {"HIGH": 3.0},
        }
        result = alerts(
            new_score_id="score-1",
            new_standing=AccountScoreStanding.RANKED,
            new_band=AccountScoreBand.HOT,
            previous_band=None,
            new_findings=[new_finding],
            active_settings=active_settings,
            alert_max_age_days=14,
            as_of=AS_OF,
            account_id="account-1",
            service_id="service-1",
        )
        from leadradar.core.enums import AlertKind

        assert not any(a.kind == AlertKind.STRONG_SIGNAL for a in result)
