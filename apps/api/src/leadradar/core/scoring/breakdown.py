"""[Score breakdown](/architecture/rules.md#score-breakdown).

`score_account(...)` and `breakdown_to_json(...)`.

Composes Recency decay, Fit, Intent, Disqualification, Priority/standing/band into the final
`ScoreResult`. Byte-identical JSON for equal inputs ([N-04](/requirements/system.md)).

No I/O.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from leadradar.core.enums import AccountScoreBand, AccountScoreStanding
from leadradar.core.scoring.disqualification import disqualify
from leadradar.core.scoring.fit import fit
from leadradar.core.scoring.intent import intent
from leadradar.core.scoring.priority import priority_standing_band
from leadradar.core.scoring.settings import ScoringSettings


def _r(v: float) -> float:
    """Round to 6 decimal places (deterministic serialisation, [N-04])."""
    return round(v, 6)


def _sort_dict(obj: object) -> object:
    """Recursively sort dict keys for deterministic JSON."""
    if isinstance(obj, dict):
        return {k: _sort_dict(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_dict(item) for item in obj]
    return obj


@dataclass(frozen=True)
class ScoreInputs:
    """All inputs that `score_account` needs."""

    account_id: str
    service_id: str
    scoring_config_id: str
    settings_version: int
    attributes: dict[str, object]
    # flat list of finding dicts: id, question_key, strength, observed_at (datetime),
    # source_type, half_life_days (int|None)
    findings: list[dict[str, object]]
    # in-force lead feedback verdict (ALREADY_CUSTOMER | RELEVANT | NOT_RELEVANT | None)
    lead_feedback_verdict: str | None
    # ACTIVE disqualifier_override dicts: rule_key, id
    active_overrides: list[dict[str, object]]
    # When provided, each dict has: question_key, weight, half_life_days, polarity.
    # When None, all question_settings from ScoringSettings are treated as POSITIVE.
    question_settings_with_polarity: list[dict[str, object]] | None = None


@dataclass(frozen=True)
class ScoreResult:
    """Output of `score_account`."""

    scoring_config_id: str
    fit: int
    intent: int
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand | None
    breakdown: dict[str, object]
    finding_ids: frozenset[str]
    override_ids: frozenset[str]


def score_account(
    inputs: ScoreInputs,
    as_of: datetime,
    settings: ScoringSettings,
) -> ScoreResult:
    """Compose all scoring rules into a `ScoreResult` with a deterministic breakdown."""
    weight_values = dict(settings.weight_values)
    strength_values = dict(settings.strength_values)
    default_half_life_days = dict(settings.default_half_life_days)

    # --- Fit ---
    icp_criteria = [c.model_dump() for c in settings.icp_criteria]
    fit_result = fit(
        attributes=inputs.attributes,
        icp_criteria=icp_criteria,
        weight_values=weight_values,
        unknown_match=settings.unknown_match,
    )

    # Augment attributes with per-criterion match label so disqualification can see ICP mismatches
    augmented_attributes: dict[str, object] = dict(inputs.attributes)
    for cr in fit_result.criteria:
        augmented_attributes[f"_icp_match_{cr.key}"] = cr.match

    # --- Intent ---
    # Build question settings list with polarity
    if inputs.question_settings_with_polarity is not None:
        q_settings_list = inputs.question_settings_with_polarity
    else:
        # Fall back to settings questions, all POSITIVE
        q_settings_list = [
            {
                "question_key": qs.question_key,
                "weight": qs.weight,
                "half_life_days": qs.half_life_days,
                "polarity": "POSITIVE",
            }
            for qs in settings.questions
        ]

    intent_result = intent(
        findings=inputs.findings,
        question_settings=q_settings_list,
        weight_values=weight_values,
        strength_values=strength_values,
        negative_factor=settings.negative_factor,
        intent_saturation=settings.intent_saturation,
        default_half_life_days=default_half_life_days,
        min_decay=settings.min_decay,
        as_of=as_of,
    )

    # --- Disqualification ---
    disq_defs = [d.model_dump() for d in settings.disqualifiers]
    disq_entries = disqualify(
        disqualifiers=disq_defs,
        attributes=augmented_attributes,
        findings=inputs.findings,
        active_overrides=inputs.active_overrides,
        min_decay=settings.min_decay,
        strength_values=strength_values,
        default_half_life_days=default_half_life_days,
        as_of=as_of,
    )

    # --- Priority, Standing, Band ---
    priority_val, standing, band = priority_standing_band(
        fit=fit_result.value,
        intent=intent_result.value,
        disq_entries=disq_entries,
        lead_feedback_verdict=inputs.lead_feedback_verdict,
        fit_weight=settings.fit_weight,
        intent_weight=settings.intent_weight,
        min_fit=settings.min_fit,
        hot_threshold=settings.hot_threshold,
        warm_threshold=settings.warm_threshold,
    )

    # --- Collect finding and override ids ---
    finding_ids: set[str] = set()
    for qr in intent_result.questions:
        if qr.finding_id is not None:
            finding_ids.add(qr.finding_id)
    for de in disq_entries:
        if de.finding_id is not None:
            finding_ids.add(de.finding_id)

    override_ids: set[str] = set()
    for de in disq_entries:
        if de.override_id is not None:
            override_ids.add(de.override_id)

    # --- Build breakdown dict ---
    fit_criteria_list = [
        {
            "key": cr.key,
            "kind": cr.kind,
            "weight": cr.weight,
            "weight_value": _r(cr.weight_value),
            "attribute": cr.attribute,
            "match": cr.match,
            "credit": _r(cr.credit),
            "points": _r(cr.points),
        }
        for cr in fit_result.criteria
    ]
    intent_questions_list = [
        {
            "question_key": qr.question_key,
            "polarity": qr.polarity,
            "weight": qr.weight,
            "weight_value": _r(qr.weight_value),
            "finding_id": qr.finding_id,
            "strength": qr.strength,
            "decay": _r(qr.decay_factor),
            "value": _r(qr.value),
            "points": _r(qr.points),
        }
        for qr in intent_result.questions
    ]
    disq_list = [
        {
            "key": de.key,
            "label": de.label,
            "matched": de.matched,
            "overridden": de.overridden,
            "override_id": de.override_id,
            "finding_id": de.finding_id,
        }
        for de in disq_entries
    ]

    breakdown: dict[str, object] = {
        "settings_version": inputs.settings_version,
        "as_of": as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fit": {
            "value": fit_result.value,
            "criteria": fit_criteria_list,
        },
        "intent": {
            "value": intent_result.value,
            "positive_sum": _r(intent_result.positive_sum),
            "negative_sum": _r(intent_result.negative_sum),
            "max_positive": _r(intent_result.max_positive),
            "questions": intent_questions_list,
        },
        "disqualifiers": disq_list,
        "priority": priority_val,
        "standing": str(standing),
        "band": str(band) if band is not None else None,
    }

    return ScoreResult(
        scoring_config_id=inputs.scoring_config_id,
        fit=fit_result.value,
        intent=intent_result.value,
        priority=priority_val,
        standing=standing,
        band=band,
        breakdown=breakdown,
        finding_ids=frozenset(finding_ids),
        override_ids=frozenset(override_ids),
    )


def breakdown_to_json(breakdown: dict[str, object]) -> str:
    """Serialize the breakdown dict to byte-identical JSON: sorted keys, 6-decimal rounding.

    The dict is already rounding-normalised by `score_account`; this function only
    sorts the keys recursively and serialises.
    """
    sorted_breakdown = _sort_dict(breakdown)
    return json.dumps(sorted_breakdown, sort_keys=True, separators=(",", ":"))
