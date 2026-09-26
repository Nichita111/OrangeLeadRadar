"""[Account identity](/architecture/rules.md#account-identity) (`S-ACC-01`, `S-ACC-02`,
`S-ACC-03`): domain and name normalisation, the two facts `accounts.commands` matches a new
account or CSV row against. Pure functions; the Public Suffix List lookup reads only the
`publicsuffix2` package's vendored offline snapshot, never the network — the standard library
has no public-suffix data, so it cannot tell `dhl.com` (a registrable domain) from `dhl.co.uk`'s
`co.uk` (a suffix with no registrable label of its own) on its own."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

import publicsuffix2

#: The legal-form and grouping tokens [Account identity]
#: (/architecture/rules.md#account-identity) drops during name normalisation.
_LEGAL_FORM_TOKENS = frozenset(
    {
        "ag",
        "se",
        "gmbh",
        "kg",
        "kgaa",
        "plc",
        "ltd",
        "limited",
        "inc",
        "corp",
        "corporation",
        "sa",
        "nv",
        "bv",
        "spa",
        "group",
        "holding",
        "co",
    }
)

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


class InvalidDomain(Exception):
    """`value` has no registrable domain ([Account identity]
    (/architecture/rules.md#account-identity)); the caller maps this to `VALIDATION`."""


def normalise_domain(value: str) -> str:
    """The registrable domain of a domain or URL: add `https://` if no scheme is present, take
    the host, lower-case it, drop a trailing dot, convert to IDNA, and reduce it to its
    registrable domain with the Public Suffix List — `https://www.Lufthansa.com/de` ->
    `lufthansa.com`, `group.dhl.com` -> `dhl.com` ([Account identity]
    (/architecture/rules.md#account-identity)). Raises `InvalidDomain` when `value` has no
    registrable domain."""
    candidate = value.strip()
    if not candidate:
        raise InvalidDomain("A domain or URL is required.")
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    host = urlsplit(candidate).hostname
    if not host:
        raise InvalidDomain(f"'{value}' has no host.")
    host = host.lower().rstrip(".")
    try:
        idna_host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise InvalidDomain(f"'{value}' is not a valid domain.") from exc
    registrable = publicsuffix2.get_sld(idna_host, strict=False)
    if not registrable or "." not in registrable:
        raise InvalidDomain(f"'{value}' has no registrable domain.")
    return registrable


def normalise_name(value: str) -> str:
    """The name after [Account identity](/architecture/rules.md#account-identity) name
    normalisation: Unicode NFKC, case-fold, replace punctuation with spaces, drop the legal-form
    and grouping tokens, and collapse whitespace — "Deutsche Lufthansa AG" ->
    `deutsche lufthansa`."""
    folded = unicodedata.normalize("NFKC", value).casefold()
    despunctuated = _PUNCTUATION_RE.sub(" ", folded)
    tokens = [token for token in despunctuated.split() if token not in _LEGAL_FORM_TOKENS]
    return _WHITESPACE_RE.sub(" ", " ".join(tokens)).strip()
