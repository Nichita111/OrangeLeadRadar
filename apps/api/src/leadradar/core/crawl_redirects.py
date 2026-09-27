"""[Fetch window](/architecture/rules.md#fetch-window) step 3, the `WEBSITE` crawler's redirect
following (decisions G8, G9, G10 of `adr-21-source-detection-timing-and-crawler-redirects.md`):
whether a page or report's answer should be followed to another address. Pure: decides from a
status and a `Location` header already in hand, never touching the network itself."""

from __future__ import annotations

from urllib.parse import urljoin

from leadradar.core.account_identity import InvalidDomain, normalise_domain

#: The redirect statuses [Fetch window](/architecture/rules.md#fetch-window) step 3 follows; 300
#: (multiple choices) and 304 (not modified) are not among them.
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


def redirect_target(request_url: str, status: int, location: str | None, domain: str) -> str | None:
    """The absolute URL `request_url`'s answer redirects to, when `status` is one of
    [`REDIRECT_STATUSES`](#redirect_statuses), `location` is present, and the resolved target is
    on the account's registrable `domain` ([Account identity]
    (/architecture/rules.md#account-identity)); `None` otherwise — so the Invariants' "A redirect
    to another registrable domain is never followed" holds, and a hop with no usable target is
    never taken as one."""
    if status not in REDIRECT_STATUSES or not location:
        return None
    target = urljoin(request_url, location)
    try:
        if normalise_domain(target) != domain:
            return None
    except InvalidDomain:
        return None
    return target
