"""Unit tests of `outreach.hubspot`'s pure request builders and `parse_company_id`, and of
`upsert_company` itself driven over an `httpx.MockTransport`
([`API-70`](/architecture/interfaces.md#crm))."""

from __future__ import annotations

import httpx
import pytest

from leadradar.outreach.company_push import CompanyPush
from leadradar.outreach.errors import CrmUnavailable
from leadradar.outreach.hubspot import (
    build_create_request,
    build_search_request,
    build_update_request,
    parse_company_id,
    upsert_company,
)

pytestmark = pytest.mark.unit


def _push() -> CompanyPush:
    return CompanyPush(
        domain="example.com",
        name="Example GmbH",
        leadradar_service="Intelligent Automation",
        leadradar_priority="73",
        leadradar_band="HOT",
        leadradar_standing="RANKED",
        leadradar_top_signals='Does it? — "Yes."',
        leadradar_url="http://localhost:8080/accounts/1",
    )


def test_search_request_targets_the_hubspot_api_and_filters_on_domain() -> None:
    request = build_search_request(_push())

    assert request.url == "https://api.hubapi.com/crm/v3/objects/companies/search"
    assert request.json["filterGroups"] == [
        {"filters": [{"propertyName": "domain", "operator": "EQ", "value": "example.com"}]}
    ]


def test_parse_company_id_returns_the_first_results_id() -> None:
    response: dict[str, object] = {
        "results": [{"id": "123", "properties": {"domain": "example.com"}}]
    }

    assert parse_company_id(response) == "123"


def test_parse_company_id_returns_none_for_an_empty_result() -> None:
    response: dict[str, object] = {"results": []}

    assert parse_company_id(response) is None


@pytest.mark.parametrize(
    "response",
    [
        {"results": "not-a-list"},
        {"results": [{"properties": {"domain": "example.com"}}]},
        {"results": [{"id": ""}]},
        {"results": [{"id": 123}]},
    ],
    ids=[
        "results-not-a-list",
        "first-result-has-no-id",
        "first-results-id-is-empty",
        "id-not-a-string",
    ],
)
def test_parse_company_id_raises_on_a_malformed_search_answer(
    response: dict[str, object],
) -> None:
    with pytest.raises(CrmUnavailable):
        parse_company_id(response)


def test_update_request_writes_exactly_the_leadradar_properties_and_nothing_else() -> None:
    request = build_update_request("123", _push())

    assert request.url == "https://api.hubapi.com/crm/v3/objects/companies/123"
    properties = request.json["properties"]
    assert isinstance(properties, dict)
    assert set(properties.keys()) == {
        "leadradar_service",
        "leadradar_priority",
        "leadradar_band",
        "leadradar_standing",
        "leadradar_top_signals",
        "leadradar_url",
    }


def test_create_request_also_carries_domain_and_name() -> None:
    request = build_create_request(_push())

    properties = request.json["properties"]
    assert isinstance(properties, dict)
    assert properties["domain"] == "example.com"
    assert properties["name"] == "Example GmbH"
    assert properties["leadradar_priority"] == "73"


async def test_upsert_company_raises_crm_unavailable_when_the_search_body_is_not_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(CrmUnavailable):
            await upsert_company(http, "a-token", _push(), timeout_s=1.0)


async def test_upsert_company_raises_crm_unavailable_when_the_upsert_body_is_not_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, content=b"not json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(CrmUnavailable):
            await upsert_company(http, "a-token", _push(), timeout_s=1.0)


async def test_upsert_company_raises_crm_unavailable_when_search_body_is_not_an_object() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(CrmUnavailable):
            await upsert_company(http, "a-token", _push(), timeout_s=1.0)


async def test_upsert_company_patches_the_matched_company_when_the_search_finds_one() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": [{"id": "123"}]})
        return httpx.Response(200, json={"id": "123"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        company_id = await upsert_company(http, "a-token", _push(), timeout_s=1.0)

    assert company_id == "123"
    assert [request.method for request in requests] == ["POST", "PATCH"]
    assert requests[1].url.path.endswith("/crm/v3/objects/companies/123")


async def test_upsert_company_creates_a_company_when_the_search_finds_none() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"id": "456"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        company_id = await upsert_company(http, "a-token", _push(), timeout_s=1.0)

    assert company_id == "456"
    assert [request.method for request in requests] == ["POST", "POST"]
    assert requests[1].url.path.endswith("/crm/v3/objects/companies")


async def test_upsert_company_raises_crm_unavailable_when_the_matched_id_is_an_empty_string() -> (
    None
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": [{"id": ""}]})
        return httpx.Response(200, json={"id": "789"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(CrmUnavailable):
            await upsert_company(http, "a-token", _push(), timeout_s=1.0)


async def test_upsert_company_raises_crm_unavailable_when_the_created_id_is_an_empty_string() -> (
    None
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"id": ""})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(CrmUnavailable):
            await upsert_company(http, "a-token", _push(), timeout_s=1.0)
