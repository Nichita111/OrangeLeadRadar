"""Unit tests of [Outreach grounding](/architecture/rules.md#outreach-grounding)'s validity check
and the [Persona mapping](/architecture/rules.md#persona-mapping) threshold (`S-OUT-01`,
`S-ACC-04`)."""

from __future__ import annotations

import pytest

from leadradar.accounts.contacts import persona_from_probabilities
from leadradar.core.enums import ContactPersona
from leadradar.core.outreach_grounding import grounding_violations

pytestmark = pytest.mark.unit

_URLS = {"f1": "https://example.com/news/1", "f2": "https://example.com/news/2"}


def _check(body: str, cited: list[str], max_chars: int = 200) -> list[str]:
    return grounding_violations(
        subject="Automation", body=body, cited_ids=cited, url_by_finding=_URLS, max_chars=max_chars
    )


def test_a_grounded_body_citing_given_findings_is_valid() -> None:
    body = "Your 2024-03-01 announcement (https://example.com/news/1.) about 1.000 processes."
    assert _check(body, ["f1"]) == []


@pytest.mark.parametrize(
    ("body", "cited", "max_chars"),
    [
        ("Hello", [], 200),
        ("Hello", ["f3"], 200),
        ("x" * 201, ["f1"], 200),
        ("See https://other.example/page", ["f1"], 200),
        ("See https://example.com/news/2", ["f1"], 200),
        ("Write to jane.doe@example.com", ["f1"], 200),
        ("Call +49 228 182 0", ["f1"], 200),
    ],
)
def test_an_output_breaking_the_rule_is_invalid(
    body: str, cited: list[str], max_chars: int
) -> None:
    assert _check(body, cited, max_chars) != []


def test_persona_below_the_threshold_is_other() -> None:
    probabilities = {"HEAD_OF_AUTOMATION": 0.5, "CIO": 0.3}
    assert persona_from_probabilities(probabilities, 0.6) is ContactPersona.OTHER
    assert persona_from_probabilities(probabilities, 0.5) is ContactPersona.HEAD_OF_AUTOMATION
