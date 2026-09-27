"""[Score breakdown](/architecture/rules.md#score-breakdown): reads `FindingView.points`
(/architecture/interfaces.md#findingview) for one finding out of a stored `breakdown`. Pure, no
I/O: the breakdown itself is read by the capability function."""

from __future__ import annotations

import uuid


def counted_points(breakdown: dict[str, object], finding_id: uuid.UUID) -> float | None:
    """The `points` of the `intent.questions[]` entry whose `finding_id` is `finding_id`, else
    `None` — the finding is not the counted finding of its question, or was never intent-scored."""
    intent = breakdown.get("intent")
    if not isinstance(intent, dict):
        return None
    questions = intent.get("questions")
    if not isinstance(questions, list):
        return None
    target = str(finding_id)
    for entry in questions:
        if isinstance(entry, dict) and entry.get("finding_id") == target:
            points = entry.get("points")
            return float(points) if points is not None else None
    return None
