"""[Disqualification](/architecture/rules.md#disqualification): `disqualify(...)`.

Pure function; no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast

from leadradar.core.scoring.decay import decay


@dataclass(frozen=True)
class DisqEntry:
    """One disqualifier result in the breakdown."""

    key: str
    label: str
    matched: bool
    overridden: bool
    override_id: str | None
    finding_id: str | None  # The finding that triggered a SIGNAL disqualifier


def disqualify(
    disqualifiers: list[dict[str, object]],
    attributes: dict[str, object],
    findings: list[dict[str, object]],
    active_overrides: list[dict[str, object]],
    min_decay: float,
    strength_values: dict[str, float],
    default_half_life_days: dict[str, int],
    as_of: datetime,
) -> list[DisqEntry]:
    """Apply all disqualifiers and return a list of DisqEntry.

    `active_overrides` is a list of dicts with at least `rule_key` and `id`.
    The account is excluded when any entry has matched=True and overridden=False.
    """
    override_by_key: dict[str, str] = {}
    for ov in active_overrides:
        override_by_key[str(ov["rule_key"])] = str(ov["id"])

    entries: list[DisqEntry] = []

    for d in disqualifiers:
        key = str(d["key"])
        label = str(d["label"])
        kind = str(d["kind"])

        matched = False
        finding_id: str | None = None

        if kind == "ICP_MISMATCH":
            criterion_key = d.get("criterion_key")
            if criterion_key is not None:
                # Scoring breakdown augments attributes with _icp_match_{criterion_key}
                attr_key = f"_icp_match_{criterion_key}"
                match_val = attributes.get(attr_key)
                if match_val == "MISMATCH":
                    matched = True

        elif kind == "SIGNAL":
            question_key = d.get("question_key")
            min_strength_label = d.get("min_strength")
            if question_key is not None and min_strength_label is not None:
                # Strength ordering: WEAK < MEDIUM < STRONG
                _strength_order = {"WEAK": 0, "MEDIUM": 1, "STRONG": 2}
                min_order = _strength_order.get(str(min_strength_label), 0)

                for f in findings:
                    if str(f["question_key"]) != str(question_key):
                        continue
                    strength_label = str(f["strength"])
                    f_order = _strength_order.get(strength_label, -1)
                    if f_order < min_order:
                        continue
                    # Check decay; findings never carry their own half_life_days so pass None
                    # and let decay() fall back to default_half_life_days[source_type].
                    d_factor = decay(
                        observed_at=cast(datetime, f["observed_at"]),
                        source_type=str(f["source_type"]),
                        half_life_days=None,
                        default_half_life_days=default_half_life_days,
                        min_decay=min_decay,
                        as_of=as_of,
                    )
                    if d_factor >= min_decay:
                        matched = True
                        finding_id = str(f["id"]) if f.get("id") is not None else None
                        break

        overridden = False
        override_id: str | None = None
        if matched and key in override_by_key:
            overridden = True
            override_id = override_by_key[key]

        entries.append(
            DisqEntry(
                key=key,
                label=label,
                matched=matched,
                overridden=overridden,
                override_id=override_id,
                finding_id=finding_id,
            )
        )

    return entries
