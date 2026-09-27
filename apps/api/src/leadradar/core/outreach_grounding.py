"""[Outreach grounding](/architecture/rules.md#outreach-grounding): the validity check of one
draft outreach output. Pure; the capability that selects the findings, calls the LLM and
retries an invalid output once is [`leadradar.outreach.drafts`](../outreach/drafts.py)."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping

_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]]+", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_CANDIDATE = re.compile(r"\+?\d[\d\s().\-/]{6,}\d")
#: A run of digits and separators counts as a phone number from nine digits on, so an ISO date
#: (eight digits) or a figure such as "1.000" is not mistaken for one.
_PHONE_MIN_DIGITS = 9
_TRAILING_PUNCTUATION = ".,;:!?"


def _normalise_url(url: str) -> str:
    return url.rstrip(_TRAILING_PUNCTUATION).rstrip("/").lower()


def _has_phone_number(text: str) -> bool:
    return any(
        sum(char.isdigit() for char in match.group()) >= _PHONE_MIN_DIGITS
        for match in _PHONE_CANDIDATE.finditer(text)
    )


def grounding_violations(
    *,
    subject: str | None,
    body: str,
    cited_ids: Collection[str],
    url_by_finding: Mapping[str, str],
    max_chars: int,
) -> list[str]:
    """Why an output breaks the rule, empty when it is valid: the cited ids are a non-empty
    subset of the findings given (`url_by_finding`, each finding's document URL); the body is at
    most `max_chars` characters; the text holds no URL except the cited findings' document URLs,
    and no email address or phone number."""
    violations: list[str] = []
    if not cited_ids:
        violations.append("cites no finding")
    elif not set(cited_ids) <= set(url_by_finding):
        violations.append("cites a finding it was not given")
    if len(body) > max_chars:
        violations.append(f"body is longer than {max_chars} characters")
    text = f"{subject or ''}\n{body}"
    allowed = {_normalise_url(url_by_finding[i]) for i in cited_ids if i in url_by_finding}
    if any(_normalise_url(match.group()) not in allowed for match in _URL.finditer(text)):
        violations.append("contains a URL that is not a cited finding's")
    if _EMAIL.search(text):
        violations.append("contains an email address")
    if _has_phone_number(text):
        violations.append("contains a phone number")
    return violations
