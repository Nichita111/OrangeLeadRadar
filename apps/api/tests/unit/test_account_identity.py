"""Unit tests of [Account identity](/architecture/rules.md#account-identity):
`core.account_identity.normalise_domain` and `normalise_name`."""

from __future__ import annotations

import pytest

from leadradar.core.account_identity import InvalidDomain, normalise_domain, normalise_name

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.Lufthansa.com/de", "lufthansa.com"),
        ("group.dhl.com", "dhl.com"),
        ("dhl.com", "dhl.com"),
        ("HTTPS://DHL.COM/", "dhl.com"),
        ("www.example.co.uk", "example.co.uk"),
        ("example.com.", "example.com"),
    ],
)
def test_normalise_domain_reduces_to_the_registrable_domain(value: str, expected: str) -> None:
    assert normalise_domain(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "not a domain", "https://localhost/"])
def test_normalise_domain_refuses_a_value_with_no_registrable_domain(value: str) -> None:
    with pytest.raises(InvalidDomain):
        normalise_domain(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Deutsche Lufthansa AG", "deutsche lufthansa"),
        ("DHL Group", "dhl"),
        ("SWISS", "swiss"),
        ("  Acme   Corp.  ", "acme"),
        ("Ærø A/S", "ærø a s"),
    ],
)
def test_normalise_name_drops_legal_forms_and_collapses_whitespace(
    value: str, expected: str
) -> None:
    assert normalise_name(value) == expected


def test_normalise_name_is_stable_when_applied_twice() -> None:
    once = normalise_name("Deutsche Lufthansa AG")
    assert normalise_name(once) == once
