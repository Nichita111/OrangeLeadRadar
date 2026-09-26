"""[Source detection](/architecture/rules.md#source-detection) (`S-ING-05`): which of an
account's home-page links, and which single web-search result, become a `DETECTED`
[`account_source`](/architecture/sql-store.md#account_source) row. Pure functions: the `WEBSITE`
and `SERPAPI` adapters (not this task) fetch the home page and run the search; this module only
decides, from links and terms already in hand, never touching the network itself."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from leadradar.core.account_identity import InvalidDomain, normalise_domain
from leadradar.core.enums import AccountSourceKind

#: [Source detection](/architecture/rules.md#source-detection) Algorithm table: the terms whose
#: presence in a link's path or text names it a candidate for the kind, checked case-insensitively.
_KIND_TERMS: dict[AccountSourceKind, tuple[str, ...]] = {
    AccountSourceKind.NEWSROOM: (
        "press",
        "news",
        "newsroom",
        "media",
        "presse",
        "medien",
        "aktuelles",
    ),
    AccountSourceKind.INVESTOR_RELATIONS: (
        "investor",
        "investors",
        "annual-report",
        "geschaeftsbericht",
        "finanzberichte",
    ),
    AccountSourceKind.CAREERS: ("careers", "career", "jobs", "karriere", "stellenangebote"),
}

#: Public applicant-tracking hosts a `CAREERS` link may be on instead of the account's own
#: domain ([Source detection](/architecture/rules.md#source-detection) Algorithm).
ATS_HOSTS: frozenset[str] = frozenset(
    {"boards.greenhouse.io", "jobs.lever.co", "jobs.smartrecruiters.com"}
)
_ATS_HOST_SUFFIX = ".myworkdayjobs.com"

#: The kinds a home page's links can fill; `RSS_FEED` is found through `<link rel="alternate">`
#: instead, and `WEBSITE` is created with the account, never detected.
_LINK_KINDS = (
    AccountSourceKind.NEWSROOM,
    AccountSourceKind.INVESTOR_RELATIONS,
    AccountSourceKind.CAREERS,
)


@dataclass(frozen=True)
class LinkCandidate:
    """One link of the home page, in document order: its resolved absolute URL and its visible
    text, both consulted for a kind's terms."""

    url: str
    text: str


@dataclass(frozen=True)
class DetectedSource:
    """One [`account_source`](/architecture/sql-store.md#account_source) row to add with origin
    `DETECTED`."""

    kind: AccountSourceKind
    url: str


def resolve_link(base_url: str, href: str) -> str:
    """The absolute URL a home page's relative `href` resolves to, from `base_url`."""
    return urljoin(base_url, href)


def _is_on_domain(url: str, domain: str) -> bool:
    try:
        return normalise_domain(url) == domain
    except InvalidDomain:
        return False


def _is_on_ats_host(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in ATS_HOSTS or host.endswith(_ATS_HOST_SUFFIX)


def _matches_terms(candidate: LinkCandidate, terms: tuple[str, ...]) -> bool:
    haystack = f"{urlsplit(candidate.url).path} {candidate.text}".lower()
    return any(term in haystack for term in terms)


def _first_link_for_kind(
    kind: AccountSourceKind, links: Iterable[LinkCandidate], domain: str
) -> str | None:
    terms = _KIND_TERMS[kind]
    for candidate in links:
        on_domain = _is_on_domain(candidate.url, domain)
        if not on_domain and not (
            kind == AccountSourceKind.CAREERS and _is_on_ats_host(candidate.url)
        ):
            continue
        if _matches_terms(candidate, terms):
            return candidate.url
    return None


def detect_home_page_sources(
    *,
    links: list[LinkCandidate],
    alternate_feed_url: str | None,
    domain: str,
    existing_kinds: frozenset[AccountSourceKind],
) -> list[DetectedSource]:
    """[Source detection](/architecture/rules.md#source-detection) Algorithm, the home-page half:
    one `DetectedSource` per kind the account has no source of yet (`existing_kinds`), in kind
    order — the first matching link for `NEWSROOM`, `INVESTOR_RELATIONS` and `CAREERS`, and
    `alternate_feed_url` (the page's `<link rel="alternate">` of type RSS or Atom, if any) for
    `RSS_FEED`. A kind with a `MANUAL` source is never detected: the caller excludes it from
    `existing_kinds` only when it is `DETECTED`, per the Invariants "A kind with a `MANUAL`
    source is never detected" — so `existing_kinds` here must already include every kind that
    has any source, `MANUAL` or `DETECTED`."""
    detected: list[DetectedSource] = []
    for kind in _LINK_KINDS:
        if kind in existing_kinds:
            continue
        url = _first_link_for_kind(kind, links, domain)
        if url is not None:
            detected.append(DetectedSource(kind=kind, url=url))
    if AccountSourceKind.RSS_FEED not in existing_kinds and alternate_feed_url:
        detected.append(DetectedSource(kind=AccountSourceKind.RSS_FEED, url=alternate_feed_url))
    return detected


#: [Source detection](/architecture/rules.md#source-detection) Algorithm, the `SERPAPI` half:
#: the query issued for each kind still missing, `"{name}" …`.
SEARCH_QUERY_SUFFIX: dict[AccountSourceKind, str] = {
    AccountSourceKind.CAREERS: "careers",
    AccountSourceKind.INVESTOR_RELATIONS: "investor relations annual report",
}


def search_query(kind: AccountSourceKind, account_name: str) -> str:
    """The `SERPAPI` query for `kind`: `'"{name}" careers'` or
    `'"{name}" investor relations annual report'`."""
    return f'"{account_name}" {SEARCH_QUERY_SUFFIX[kind]}'


def first_result_on_domain(result_urls: list[str], domain: str) -> str | None:
    """The first of a web search's result URLs that is on the account's domain, or `None`."""
    for url in result_urls:
        if _is_on_domain(url, domain):
            return url
    return None
