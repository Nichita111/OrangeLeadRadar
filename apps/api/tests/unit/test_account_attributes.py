"""Unit tests of [Account attributes](/architecture/rules.md#account-attributes)'s pure
decisions (`S-ING-06`): the precedence a plug-in or the classifier writes under, and the
operational-complexity level a classifier answer resolves to."""

from __future__ import annotations

import pytest

from leadradar.core.account_attributes import (
    operational_complexity_from_probabilities,
    should_write_attribute,
)
from leadradar.core.enums import AccountOperationalComplexity

pytestmark = pytest.mark.unit


def test_a_null_value_is_writable_whatever_its_origin() -> None:
    for current_origin in (None, "MANUAL", "CRUNCHBASE", "CLASSIFIER"):
        assert should_write_attribute(
            current_value_is_null=True, current_origin=current_origin, new_origin="CLASSIFIER"
        )


def test_crunchbase_over_classifier_is_written() -> None:
    assert should_write_attribute(
        current_value_is_null=False, current_origin="CLASSIFIER", new_origin="CRUNCHBASE"
    )


def test_equal_origins_are_not_written() -> None:
    assert not should_write_attribute(
        current_value_is_null=False, current_origin="CRUNCHBASE", new_origin="CRUNCHBASE"
    )


@pytest.mark.parametrize("current_origin", ["CRUNCHBASE", "MANUAL"])
def test_classifier_never_overwrites_a_higher_precedence_value(current_origin: str) -> None:
    assert not should_write_attribute(
        current_value_is_null=False, current_origin=current_origin, new_origin="CLASSIFIER"
    )


def test_the_most_probable_level_at_or_above_min_p_is_chosen() -> None:
    probabilities = {"LOW": 0.1, "MEDIUM": 0.6, "HIGH": 0.3}
    assert (
        operational_complexity_from_probabilities(probabilities, 0.6)
        == AccountOperationalComplexity.MEDIUM
    )


def test_just_below_min_p_leaves_the_attribute_unknown() -> None:
    probabilities = {"LOW": 0.1, "MEDIUM": 0.599, "HIGH": 0.301}
    assert operational_complexity_from_probabilities(probabilities, 0.6) is None


def test_just_above_min_p_is_chosen() -> None:
    probabilities = {"LOW": 0.1, "MEDIUM": 0.601, "HIGH": 0.299}
    assert (
        operational_complexity_from_probabilities(probabilities, 0.6)
        == AccountOperationalComplexity.MEDIUM
    )


def test_no_probabilities_leaves_the_attribute_unknown() -> None:
    assert operational_complexity_from_probabilities({}, 0.6) is None
