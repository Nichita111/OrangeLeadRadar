"""The HubSpot adapter of [`API-70`](/architecture/interfaces.md#crm): CRM v3 companies API at
`HUBSPOT_API_URL`, search by `domain`, then update or create. The adapter never creates or
inspects HubSpot properties; the portal's administrator creates the `leadradar_*` properties by
hand, as [`CompanyPush`](/architecture/interfaces.md#companypush) states. The request builders
and `parse_company_id` are pure and unit-tested; `upsert_company` is unit-tested directly over
an `httpx.MockTransport`, without a socket."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from leadradar.outreach.company_push import CompanyPush
from leadradar.outreach.errors import CrmUnavailable

HUBSPOT_API_URL = "https://api.hubapi.com"
_SEARCH_PATH = "/crm/v3/objects/companies/search"
_COMPANIES_PATH = "/crm/v3/objects/companies"
_SEARCH_LIMIT = 1


@dataclass(frozen=True)
class HubspotRequest:
    """One HTTP request `upsert_company` sends, built by a pure function so its shape is
    unit-tested without a socket."""

    method: str
    url: str
    json: dict[str, object]


def build_search_request(push: CompanyPush) -> HubspotRequest:
    """A CRM v3 company search filtered on `domain` equal to `push.domain`."""
    return HubspotRequest(
        method="POST",
        url=f"{HUBSPOT_API_URL}{_SEARCH_PATH}",
        json={
            "filterGroups": [
                {"filters": [{"propertyName": "domain", "operator": "EQ", "value": push.domain}]}
            ],
            "properties": ["domain"],
            "limit": _SEARCH_LIMIT,
        },
    )


def _require_company_id(value: object) -> str:
    """`value` as a non-empty string company id. Raises `CrmUnavailable` otherwise: a HubSpot id
    is never read as present when it is missing, non-string or empty
    ([Degradation](/architecture/overview.md#degradation))."""
    if not isinstance(value, str) or value == "":
        raise CrmUnavailable("HubSpot did not return a company id.")
    return value


def parse_company_id(search_response: dict[str, object]) -> str | None:
    """The `id` of the search's first result, or `None` when `results` is an empty list — "no
    company with this domain". Raises `CrmUnavailable` when `results` is missing or not a list,
    or the first result has no non-empty string `id`: a malformed 2xx answer is never read as "no
    company" ([Degradation](/architecture/overview.md#degradation))."""
    results = search_response.get("results")
    if not isinstance(results, list):
        raise CrmUnavailable("HubSpot's search answer has no results list.")
    if not results:
        return None
    first = results[0]
    first_id = first.get("id") if isinstance(first, dict) else None
    return _require_company_id(first_id)


def _leadradar_properties(push: CompanyPush) -> dict[str, str]:
    return {
        "leadradar_service": push.leadradar_service,
        "leadradar_priority": push.leadradar_priority,
        "leadradar_band": push.leadradar_band,
        "leadradar_standing": push.leadradar_standing,
        "leadradar_top_signals": push.leadradar_top_signals,
        "leadradar_url": push.leadradar_url,
    }


def build_update_request(company_id: str, push: CompanyPush) -> HubspotRequest:
    """Writes exactly the `leadradar_*` properties of `push` onto the matched company; never
    `domain` or `name`, which the company already carries."""
    return HubspotRequest(
        method="PATCH",
        url=f"{HUBSPOT_API_URL}{_COMPANIES_PATH}/{company_id}",
        json={"properties": _leadradar_properties(push)},
    )


def build_create_request(push: CompanyPush) -> HubspotRequest:
    """Creates a company with `domain`, `name` and the `leadradar_*` properties of `push`."""
    return HubspotRequest(
        method="POST",
        url=f"{HUBSPOT_API_URL}{_COMPANIES_PATH}",
        json={
            "properties": {"domain": push.domain, "name": push.name, **_leadradar_properties(push)}
        },
    )


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"HubSpot answered {response.status_code}."
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return str(body["message"])
    return f"HubSpot answered {response.status_code}."


def _json_body(response: httpx.Response) -> dict[str, object]:
    """The parsed JSON body of a 2xx answer. Raises `CrmUnavailable` when the body is not valid
    JSON or not a JSON object, matching how a non-2xx answer is treated
    ([Degradation](/architecture/overview.md#degradation))."""
    try:
        body = response.json()
    except ValueError as exc:
        raise CrmUnavailable(
            f"HubSpot answered {response.status_code} with a body that is not JSON."
        ) from exc
    if not isinstance(body, dict):
        raise CrmUnavailable(
            f"HubSpot answered {response.status_code} with a body that is not an object."
        )
    return body


async def upsert_company(
    http: httpx.AsyncClient, token: str, push: CompanyPush, timeout_s: float
) -> str:
    """Searches HubSpot for a company matching `push.domain`, then updates the match or creates
    a company, and returns the HubSpot company id. Raises `CrmUnavailable` on a transport error,
    a timeout, or any non-2xx or malformed answer
    ([Degradation](/architecture/overview.md#degradation))."""
    headers = {"Authorization": f"Bearer {token}"}
    search = build_search_request(push)
    try:
        search_response = await http.request(
            search.method, search.url, json=search.json, headers=headers, timeout=timeout_s
        )
    except httpx.HTTPError as exc:
        raise CrmUnavailable(f"HubSpot is unreachable: {exc}") from exc
    if not search_response.is_success:
        raise CrmUnavailable(_error_message(search_response))

    company_id = parse_company_id(_json_body(search_response))
    upsert = (
        build_update_request(company_id, push)
        if company_id is not None
        else build_create_request(push)
    )
    try:
        response = await http.request(
            upsert.method, upsert.url, json=upsert.json, headers=headers, timeout=timeout_s
        )
    except httpx.HTTPError as exc:
        raise CrmUnavailable(f"HubSpot is unreachable: {exc}") from exc
    if not response.is_success:
        raise CrmUnavailable(_error_message(response))

    if company_id is not None:
        return company_id
    return _require_company_id(_json_body(response).get("id"))
