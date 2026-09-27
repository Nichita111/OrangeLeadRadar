"""[Rescoring](/architecture/rules.md#rescoring) decision: `rescore_decision(...)`.

Pure function; no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from leadradar.core.scoring.breakdown import ScoreResult


@dataclass(frozen=True)
class WriteNewRow:
    """Caller must insert a new `account_score` row and clear the previous `is_current`."""

    result: ScoreResult


@dataclass(frozen=True)
class NoChange:
    """The stored score is identical; write nothing."""


def rescore_decision(
    new: ScoreResult,
    current_row: dict[str, object] | None,
) -> WriteNewRow | NoChange:
    """Compare `new` against the current stored row.

    Compares: `scoring_config_id`, `fit`, `intent`, `priority`, `standing`, `band`,
    the set of finding ids and the set of override ids in the breakdown.

    Returns `WriteNewRow` when any of these differ (or there is no current row),
    otherwise `NoChange`.
    """
    if current_row is None:
        return WriteNewRow(result=new)

    if str(current_row.get("scoring_config_id", "")) != new.scoring_config_id:
        return WriteNewRow(result=new)
    if int(str(current_row.get("fit", -1))) != new.fit:
        return WriteNewRow(result=new)
    if int(str(current_row.get("intent", -1))) != new.intent:
        return WriteNewRow(result=new)
    if int(str(current_row.get("priority", -1))) != new.priority:
        return WriteNewRow(result=new)
    if str(current_row.get("standing", "")) != str(new.standing):
        return WriteNewRow(result=new)
    stored_band = current_row.get("band")
    new_band_str = str(new.band) if new.band is not None else None
    if (str(stored_band) if stored_band is not None else None) != new_band_str:
        return WriteNewRow(result=new)

    stored_finding_ids = _extract_finding_ids(current_row)
    if stored_finding_ids != new.finding_ids:
        return WriteNewRow(result=new)

    stored_override_ids = _extract_override_ids(current_row)
    if stored_override_ids != new.override_ids:
        return WriteNewRow(result=new)

    return NoChange()


def _extract_finding_ids(row: dict[str, object]) -> frozenset[str]:
    """Extract the set of finding ids from a stored breakdown dict."""
    breakdown = row.get("breakdown")
    if not isinstance(breakdown, dict):
        return frozenset()
    ids: set[str] = set()
    intent_part = breakdown.get("intent")
    if isinstance(intent_part, dict):
        for q in intent_part.get("questions", []):
            if isinstance(q, dict) and q.get("finding_id") is not None:
                ids.add(str(q["finding_id"]))
    for disq in breakdown.get("disqualifiers", []):
        if isinstance(disq, dict) and disq.get("finding_id") is not None:
            ids.add(str(disq["finding_id"]))
    return frozenset(ids)


def _extract_override_ids(row: dict[str, object]) -> frozenset[str]:
    """Extract the set of override ids from a stored breakdown dict."""
    breakdown = row.get("breakdown")
    if not isinstance(breakdown, dict):
        return frozenset()
    ids: set[str] = set()
    for disq in breakdown.get("disqualifiers", []):
        if isinstance(disq, dict) and disq.get("override_id") is not None:
            ids.add(str(disq["override_id"]))
    return frozenset(ids)
