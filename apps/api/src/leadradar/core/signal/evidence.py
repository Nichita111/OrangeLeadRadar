# -*- coding: ascii -*-
"""[Evidence extraction](/architecture/rules.md#evidence-extraction): pure validation of a
verbatim quote against its source passage.

No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

# Typographic-to-ASCII character mapping applied before the substring check.
# Source: [Evidence extraction](/architecture/rules.md#evidence-extraction).
# All values are ASCII characters (written as string literals for clarity).
_TYPOGRAPHIC_MAP: dict[int, str] = {
    # Quotation marks -> straight double quote (ASCII 0x22)
    0x201C: "\x22",  # U+201C LEFT DOUBLE QUOTATION MARK
    0x201D: "\x22",  # U+201D RIGHT DOUBLE QUOTATION MARK
    0x201E: "\x22",  # U+201E DOUBLE LOW-9 QUOTATION MARK
    0x201F: "\x22",  # U+201F DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    # Single quotation marks -> straight apostrophe (ASCII 0x27)
    0x2018: "\x27",  # U+2018 LEFT SINGLE QUOTATION MARK
    0x2019: "\x27",  # U+2019 RIGHT SINGLE QUOTATION MARK
    0x201A: "\x27",  # U+201A SINGLE LOW-9 QUOTATION MARK
    0x201B: "\x27",  # U+201B SINGLE HIGH-REVERSED-9 QUOTATION MARK
    # Angle quotation marks -> straight double quote
    0x00AB: "\x22",  # U+00AB LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
    0x00BB: "\x22",  # U+00BB RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
    # Single angle quotation marks -> straight apostrophe
    0x2039: "\x27",  # U+2039 SINGLE LEFT-POINTING ANGLE QUOTATION MARK
    0x203A: "\x27",  # U+203A SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
    # Apostrophes -> straight apostrophe
    0x02BC: "\x27",  # U+02BC MODIFIER LETTER APOSTROPHE
    0x02B9: "\x27",  # U+02B9 MODIFIER LETTER PRIME
    # Dashes -> hyphen-minus (ASCII 0x2D)
    0x2013: "\x2d",  # U+2013 EN DASH
    0x2014: "\x2d",  # U+2014 EM DASH
    0x2015: "\x2d",  # U+2015 HORIZONTAL BAR
    0x2212: "\x2d",  # U+2212 MINUS SIGN
    # Ellipsis -> three dots
    0x2026: "...",  # U+2026 HORIZONTAL ELLIPSIS
}


def _normalise(text: str) -> str:
    """Collapse whitespace and map typographic characters to ASCII equivalents."""
    return _normalise_with_offsets(text)[0]


def _normalise_with_offsets(text: str) -> tuple[str, list[int], list[int]]:
    """The normalised text, and for each of its characters the offset of the original
    character it comes from and the offset just after it."""
    chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    for offset, char in enumerate(text):
        if char.isspace():
            if chars and chars[-1] == " ":
                ends[-1] = offset + 1
            else:
                chars.append(" ")
                starts.append(offset)
                ends.append(offset + 1)
            continue
        for mapped in _TYPOGRAPHIC_MAP.get(ord(char), char):
            chars.append(mapped)
            starts.append(offset)
            ends.append(offset + 1)
    while chars and chars[-1] == " ":
        chars.pop()
        starts.pop()
        ends.pop()
    while chars and chars[0] == " ":
        chars.pop(0)
        starts.pop(0)
        ends.pop(0)
    return "".join(chars), starts, ends


@dataclass(frozen=True)
class QuoteValidationResult:
    """Outcome of ``validate_quote``."""

    valid: bool
    reason: str | None  # None when valid
    #: The passage's own text at the matched place; None unless valid.
    span: str | None = None


def validate_quote(
    *,
    quote: str,
    passage: str,
    lang: str,
    quote_en: str | None,
    rationale: str,
    evidence_min_quote_chars: int,
    evidence_max_quote_chars: int,
    evidence_max_rationale_chars: int,
) -> QuoteValidationResult:
    """Validate the LLM's evidence output against the passage and the configuration.

    Implements [Evidence extraction](/architecture/rules.md#evidence-extraction):

    - ``quote``, after whitespace-collapsing and typographic normalisation, must be a
      substring of the normalised passage and between ``EVIDENCE_MIN_QUOTE_CHARS`` and
      ``EVIDENCE_MAX_QUOTE_CHARS`` characters.
    - ``quote_en`` must be present when ``lang`` is not ``"en"`` and absent when it is.
    - ``rationale`` must be at most ``EVIDENCE_MAX_RATIONALE_CHARS`` characters.
    """
    norm_quote = _normalise(quote)
    norm_passage, starts, ends = _normalise_with_offsets(passage)

    if len(norm_quote) < evidence_min_quote_chars:
        return QuoteValidationResult(
            valid=False,
            reason=f"quote too short: {len(norm_quote)} < {evidence_min_quote_chars}",
        )
    if len(norm_quote) > evidence_max_quote_chars:
        return QuoteValidationResult(
            valid=False,
            reason=f"quote too long: {len(norm_quote)} > {evidence_max_quote_chars}",
        )
    match = norm_passage.find(norm_quote)
    if match < 0:
        return QuoteValidationResult(
            valid=False,
            reason="quote is not a substring of the passage after normalisation",
        )

    is_english = lang.lower().startswith("en")
    if not is_english and not quote_en:
        return QuoteValidationResult(
            valid=False,
            reason=f"quote_en required for non-English document (lang={lang!r})",
        )
    if is_english and quote_en is not None:
        return QuoteValidationResult(
            valid=False,
            reason="quote_en must be absent for English documents",
        )

    if len(rationale) > evidence_max_rationale_chars:
        return QuoteValidationResult(
            valid=False,
            reason=(f"rationale too long: {len(rationale)} > {evidence_max_rationale_chars}"),
        )

    span = passage[starts[match] : ends[match + len(norm_quote) - 1]]
    return QuoteValidationResult(valid=True, reason=None, span=span)
