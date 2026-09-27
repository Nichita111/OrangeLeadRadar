"""[Feedback effects](/architecture/rules.md#feedback-effects) (`S-EVL-01`, `S-EVL-02`), with D1
applied: the status and label rules the api's feedback capability applies when it writes a lead
or finding verdict. Pure functions, no I/O; the rescore and the audit row are the capability
function's job.
"""

from __future__ import annotations

from dataclasses import dataclass

from leadradar.core.enums import (
    EvaluationItemStatus,
    FindingFeedbackVerdict,
    FindingStatus,
    FindingStrength,
)


def finding_status_after(
    status: FindingStatus, verdict: FindingFeedbackVerdict, *, revision_is_current: bool
) -> FindingStatus:
    """The finding's new `status` after a verdict
    ([Feedback effects](/architecture/rules.md#feedback-effects)): `WRONG` on an `ACTIVE` finding
    gives `REJECTED`; `CORRECT` on a `REJECTED` finding of the current revision gives `ACTIVE`;
    every other combination leaves `status` unchanged."""
    if verdict == FindingFeedbackVerdict.WRONG and status == FindingStatus.ACTIVE:
        return FindingStatus.REJECTED
    if (
        verdict == FindingFeedbackVerdict.CORRECT
        and status == FindingStatus.REJECTED
        and revision_is_current
    ):
        return FindingStatus.ACTIVE
    return status


@dataclass(frozen=True)
class DerivedLabel:
    """The `expected_strength` and `status` a
    [`evaluation_item`](/architecture/sql-store.md#evaluation_item) derived from finding feedback
    is written or updated with. `labelled_by` is not part of this pure value: it is the acting
    user, applied by the capability function."""

    expected_strength: FindingStrength
    status: EvaluationItemStatus


def derived_label(
    verdict: FindingFeedbackVerdict,
    finding_strength: FindingStrength,
    *,
    revision_is_current: bool,
    manual_label_exists: bool,
) -> DerivedLabel | None:
    """The label finding feedback derives
    ([Feedback effects](/architecture/rules.md#feedback-effects) third bullet, D1): `None` when a
    `MANUAL` item exists for the pair; otherwise `expected_strength` is the finding's own strength
    for `CORRECT` and `NONE` for `WRONG`, and `status` is `ACTIVE` for the question's current
    revision, else `STALE`."""
    if manual_label_exists:
        return None
    expected_strength = (
        finding_strength if verdict == FindingFeedbackVerdict.CORRECT else FindingStrength.NONE
    )
    status = EvaluationItemStatus.ACTIVE if revision_is_current else EvaluationItemStatus.STALE
    return DerivedLabel(expected_strength=expected_strength, status=status)
