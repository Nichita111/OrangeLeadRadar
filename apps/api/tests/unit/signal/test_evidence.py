"""Unit tests for [Evidence extraction](/architecture/rules.md#evidence-extraction).

Covers:
  - Verbatim substring after whitespace/typographic normalisation is valid
  - A non-substring is invalid
  - ``quote_en`` required for non-``en`` and forbidden for ``en``
  - Length bounds (EVIDENCE_MIN_QUOTE_CHARS, EVIDENCE_MAX_QUOTE_CHARS)
  - Rationale length enforced (EVIDENCE_MAX_RATIONALE_CHARS)
"""

from __future__ import annotations

from typing import Any

import pytest

from leadradar.core.signal.evidence import validate_quote

pytestmark = pytest.mark.unit

MIN_Q = 20
MAX_Q = 400
MAX_R = 300

PASSAGE = (
    "The company announced a major cost-reduction programme, targeting savings of "
    "EUR 500m over three years through process automation."
)
QUOTE = "major cost-reduction programme, targeting savings of EUR 500m"
RATIONALE = (
    "The passage explicitly states a cost-reduction programme with a defined savings target."
)


def _valid(**overrides: object) -> bool:
    kwargs: dict[str, Any] = dict(
        quote=QUOTE,
        passage=PASSAGE,
        lang="en",
        quote_en=None,
        rationale=RATIONALE,
        evidence_min_quote_chars=MIN_Q,
        evidence_max_quote_chars=MAX_Q,
        evidence_max_rationale_chars=MAX_R,
    )
    kwargs.update(overrides)
    return validate_quote(**kwargs).valid


class TestSubstringCheck:
    def test_verbatim_substring_is_valid(self) -> None:
        assert _valid()

    def test_non_substring_is_invalid(self) -> None:
        assert not _valid(quote="This text does not appear in the passage at all ever")

    def test_typographic_apostrophe_normalised(self) -> None:
        # Right single quotation mark U+2019 in passage -> apostrophe in quote
        passage = "The company’s programme targets 500m in savings over three years."
        quote = "The company's programme targets 500m"
        assert _valid(quote=quote, passage=passage, rationale="A sentence of 20 chars or more here")

    def test_em_dash_normalised(self) -> None:
        # Em dash U+2014 in passage -> hyphen in quote
        passage = "Savings target — EUR 500m over three years through automation."
        quote = "Savings target - EUR 500m"
        assert _valid(quote=quote, passage=passage, rationale="A valid rationale sentence here OK")

    def test_ellipsis_normalised(self) -> None:
        # Horizontal ellipsis U+2026 in passage -> three dots in quote
        passage = "The programme spans many markets… including Germany and France."
        quote = "The programme spans many markets... including Germany"
        assert _valid(quote=quote, passage=passage, rationale="A valid rationale sentence here OK")

    def test_whitespace_collapse(self) -> None:
        # Extra whitespace in quote collapses to single space
        passage = "Process automation delivers operational efficiency gains."
        quote = "Process  automation  delivers"
        assert _valid(quote=quote, passage=passage, rationale="A valid rationale sentence here OK")


class TestLengthBounds:
    def test_quote_too_short(self) -> None:
        assert not _valid(quote="Short quote.")

    def test_quote_exactly_at_min(self) -> None:
        passage = "A" * MIN_Q + " extra text that extends the passage length further."
        quote = "A" * MIN_Q
        assert _valid(quote=quote, passage=passage, rationale="A valid rationale sentence here OK")

    def test_quote_too_long(self) -> None:
        long_passage = "X" * (MAX_Q + 1) + " more text."
        long_quote = "X" * (MAX_Q + 1)
        assert not _valid(quote=long_quote, passage=long_passage)

    def test_quote_exactly_at_max(self) -> None:
        long_passage = "Y" * MAX_Q + " Z"
        long_quote = "Y" * MAX_Q
        assert _valid(quote=long_quote, passage=long_passage, rationale="Sentence here is OK.")

    def test_rationale_too_long(self) -> None:
        assert not _valid(rationale="X" * (MAX_R + 1))

    def test_rationale_exactly_at_max(self) -> None:
        assert _valid(rationale="X" * MAX_R)


class TestQuoteEn:
    def test_non_english_requires_quote_en(self) -> None:
        assert not _valid(lang="de", quote_en=None)

    def test_non_english_with_quote_en_is_valid(self) -> None:
        assert _valid(lang="de", quote_en="A cost-reduction programme targeting EUR 500m savings.")

    def test_english_must_not_have_quote_en(self) -> None:
        assert not _valid(lang="en", quote_en="Some translation")

    def test_english_without_quote_en_is_valid(self) -> None:
        assert _valid(lang="en", quote_en=None)

    def test_lang_en_gb_is_treated_as_english(self) -> None:
        """lang starting with 'en' (e.g. 'en-GB') is treated as English."""
        assert _valid(lang="en-GB", quote_en=None)


class TestSpan:
    def _result(self, **overrides: object) -> Any:
        kwargs: dict[str, Any] = dict(
            quote=QUOTE,
            passage=PASSAGE,
            lang="en",
            quote_en=None,
            rationale=RATIONALE,
            evidence_min_quote_chars=MIN_Q,
            evidence_max_quote_chars=MAX_Q,
            evidence_max_rationale_chars=MAX_R,
        )
        kwargs.update(overrides)
        return validate_quote(**kwargs)

    def test_span_is_the_passage_text_at_the_match(self) -> None:
        passage = "Intro. The company’s\n  programme — EUR 500m… goes on."
        result = self._result(
            quote="The company's programme - EUR 500m...", passage=passage, rationale="ok"
        )
        assert result.valid
        assert result.span == "The company’s\n  programme — EUR 500m…"

    def test_span_of_a_quote_at_the_minimum_and_maximum_length(self) -> None:
        low = self._result(quote="A" * MIN_Q, passage="x " + "A" * MIN_Q + " y", rationale="ok")
        high = self._result(quote="Y" * MAX_Q, passage="Y" * MAX_Q + " Z", rationale="ok")
        assert low.span == "A" * MIN_Q
        assert high.span == "Y" * MAX_Q

    def test_an_invalid_result_has_no_span(self) -> None:
        assert self._result(quote="This text does not appear in the passage at all").span is None
        assert self._result(lang="de", quote_en=None).span is None
