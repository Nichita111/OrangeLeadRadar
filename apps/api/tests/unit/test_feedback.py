"""Unit tests of [Feedback effects](/architecture/rules.md#feedback-effects) with D1:
`core.feedback.finding_status_after` and `core.feedback.derived_label`."""

from __future__ import annotations

import pytest

from leadradar.core.enums import (
    EvaluationItemStatus,
    FindingFeedbackVerdict,
    FindingStatus,
    FindingStrength,
)
from leadradar.core.feedback import DerivedLabel, derived_label, finding_status_after

pytestmark = pytest.mark.unit


def test_wrong_on_an_active_finding_gives_rejected() -> None:
    result = finding_status_after(
        FindingStatus.ACTIVE, FindingFeedbackVerdict.WRONG, revision_is_current=True
    )
    assert result == FindingStatus.REJECTED


@pytest.mark.parametrize("status", [FindingStatus.REJECTED, FindingStatus.SUPERSEDED])
def test_wrong_leaves_a_non_active_finding_unchanged(status: FindingStatus) -> None:
    result = finding_status_after(status, FindingFeedbackVerdict.WRONG, revision_is_current=True)
    assert result == status


def test_correct_on_a_rejected_finding_of_the_current_revision_gives_active() -> None:
    result = finding_status_after(
        FindingStatus.REJECTED, FindingFeedbackVerdict.CORRECT, revision_is_current=True
    )
    assert result == FindingStatus.ACTIVE


def test_correct_on_a_rejected_finding_of_an_older_revision_leaves_it_rejected() -> None:
    result = finding_status_after(
        FindingStatus.REJECTED, FindingFeedbackVerdict.CORRECT, revision_is_current=False
    )
    assert result == FindingStatus.REJECTED


@pytest.mark.parametrize("status", [FindingStatus.ACTIVE, FindingStatus.SUPERSEDED])
def test_correct_leaves_a_non_rejected_finding_unchanged(status: FindingStatus) -> None:
    result = finding_status_after(status, FindingFeedbackVerdict.CORRECT, revision_is_current=True)
    assert result == status


def test_wrong_derives_none_strength() -> None:
    label = derived_label(
        FindingFeedbackVerdict.WRONG,
        FindingStrength.STRONG,
        revision_is_current=True,
        manual_label_exists=False,
    )
    assert label == DerivedLabel(FindingStrength.NONE, EvaluationItemStatus.ACTIVE)


@pytest.mark.parametrize(
    "strength", [FindingStrength.WEAK, FindingStrength.MEDIUM, FindingStrength.STRONG]
)
def test_correct_derives_the_findings_own_strength(strength: FindingStrength) -> None:
    label = derived_label(
        FindingFeedbackVerdict.CORRECT,
        strength,
        revision_is_current=True,
        manual_label_exists=False,
    )
    assert label == DerivedLabel(strength, EvaluationItemStatus.ACTIVE)


@pytest.mark.parametrize("verdict", [FindingFeedbackVerdict.WRONG, FindingFeedbackVerdict.CORRECT])
def test_no_derived_label_when_a_manual_label_exists(verdict: FindingFeedbackVerdict) -> None:
    label = derived_label(
        verdict, FindingStrength.STRONG, revision_is_current=True, manual_label_exists=True
    )
    assert label is None


def test_derived_label_is_active_for_the_current_revision() -> None:
    label = derived_label(
        FindingFeedbackVerdict.CORRECT,
        FindingStrength.WEAK,
        revision_is_current=True,
        manual_label_exists=False,
    )
    assert label is not None
    assert label.status == EvaluationItemStatus.ACTIVE


def test_derived_label_is_stale_for_an_older_revision() -> None:
    label = derived_label(
        FindingFeedbackVerdict.CORRECT,
        FindingStrength.WEAK,
        revision_is_current=False,
        manual_label_exists=False,
    )
    assert label is not None
    assert label.status == EvaluationItemStatus.STALE
