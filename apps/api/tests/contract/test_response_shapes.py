"""Every REST contract names its request and response shapes after
[interfaces](/architecture/interfaces.md): the OpenAPI `$ref` matches the shape linked in the
"Request → response" column, including `T[]`, `Page<T>` and `204`."""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI

from leadradar.core.enums import FindingFeedbackVerdict, LeadFeedbackVerdict

from .interfaces_parsing import (
    ContractRow,
    as_list,
    as_object,
    generic_base_name,
    object_at,
    parse_interfaces,
    rest_contracts,
    value_at,
)

pytestmark = pytest.mark.contract

_REF_RE = re.compile(r"\[`(\w+)`\]\(#[\w-]+\)(`\[\]`)?")

_, _SHAPE_NAMES = parse_interfaces()


def _expected_response(row: ContractRow) -> tuple[str, str | None]:
    response_text = row.request_response.split("→", 1)[-1].strip()
    if response_text.strip("`") == "204":
        return ("none", None)
    match = _REF_RE.search(response_text)
    if not match:
        raise AssertionError(f"cannot read the response shape of {row.id}: {response_text!r}")
    name, array_marker = match.groups()
    if "Page<" in response_text:
        return ("scalar", f"Page_{name}_")
    return ("array" if array_marker else "scalar", name)


def _expected_request(row: ContractRow) -> str | None:
    left = row.request_response.split("→", 1)[0].strip()
    if left.startswith(("—", "query", "multipart")):
        return None
    match = _REF_RE.search(left)
    if not match:
        raise AssertionError(f"cannot read the request shape of {row.id}: {left!r}")
    return match.group(1)


def _actual_response(schema: dict[str, object], row: ContractRow) -> tuple[str, str | None]:
    operation = object_at(schema, "paths", f"/api/v1{row.path}", row.method.lower())
    responses = object_at(operation, "responses")
    success_code = next(code for code in responses if code.startswith("2"))
    body = as_object(responses[success_code], f"{row.id} response")
    if "content" not in body:
        return ("none", None)
    response_schema = object_at(body, "content", "application/json", "schema")
    if "$ref" in response_schema:
        ref = response_schema["$ref"]
        if not isinstance(ref, str):
            raise AssertionError(f"{row.id} response ref must be a string")
        return ("scalar", _component_name(schema, ref))
    if response_schema.get("type") == "array":
        ref = value_at(response_schema, "items", "$ref")
        if not isinstance(ref, str):
            raise AssertionError(f"{row.id} array item ref must be a string")
        return ("array", _component_name(schema, ref))
    raise AssertionError(f"cannot read the served response shape of {row.id}: {response_schema!r}")


def _component_name(schema: dict[str, object], ref: str) -> str:
    """A `$ref`'s component name, read back as the one shape interfaces.md names when the
    component is a parametrised generic instantiation of that shape."""
    component_name = ref.rsplit("/", 1)[-1]
    title = object_at(schema, "components", "schemas", component_name).get("title")
    return generic_base_name(title, _SHAPE_NAMES) or component_name


def _actual_request(schema: dict[str, object], row: ContractRow) -> str | None:
    operation = object_at(schema, "paths", f"/api/v1{row.path}", row.method.lower())
    request_body = operation.get("requestBody")
    if not request_body:
        return None
    content = object_at(request_body, "content")
    json_content = content.get("application/json")
    if not json_content:
        return None  # multipart, e.g. `API-22`
    ref = object_at(json_content, "schema").get("$ref")
    if not isinstance(ref, str):
        return None
    component_name = ref.rsplit("/", 1)[-1]
    component = object_at(schema, "components", "schemas", component_name)
    title = component.get("title")
    generic_base = generic_base_name(title, _SHAPE_NAMES)
    if generic_base:
        return generic_base
    return title if isinstance(title, str) else component_name


@pytest.mark.parametrize("row", rest_contracts(), ids=lambda row: row.id)
def test_each_route_names_its_response_shape_after_interfaces(
    row: ContractRow, app: FastAPI
) -> None:
    schema = app.openapi()
    assert _actual_response(schema, row) == _expected_response(row)


@pytest.mark.parametrize("row", rest_contracts(), ids=lambda row: row.id)
def test_each_route_names_its_request_shape_after_interfaces(
    row: ContractRow, app: FastAPI
) -> None:
    schema = app.openapi()
    assert _actual_request(schema, row) == _expected_request(row)


def test_refresh_account_declares_new_and_existing_run_responses(app: FastAPI) -> None:
    responses = object_at(
        app.openapi(), "paths", "/api/v1/accounts/{id}/refresh", "post", "responses"
    )

    assert {"200", "202"} <= responses.keys()
    for status in ("200", "202"):
        assert object_at(responses, status, "content", "application/json", "schema") == {
            "$ref": "#/components/schemas/Run"
        }


def test_alert_band_change_uses_the_contracts_from_field(app: FastAPI) -> None:
    properties = object_at(app.openapi(), "components", "schemas", "AlertBandChange", "properties")

    assert set(properties) == {"from", "to"}


@pytest.mark.parametrize(
    ("path", "verdict_enum"),
    [
        ("/api/v1/accounts/{id}/scores/{service_id}/feedback", LeadFeedbackVerdict),
        ("/api/v1/findings/{id}/feedback", FindingFeedbackVerdict),
    ],
    ids=["API-46", "API-47"],
)
def test_each_feedback_contract_accepts_only_its_verdicts(
    path: str,
    verdict_enum: type[LeadFeedbackVerdict] | type[FindingFeedbackVerdict],
    app: FastAPI,
) -> None:
    """`API-46`'s request accepts exactly the `lead_feedback` verdict values and `API-47`'s
    exactly the `finding_feedback` ones
    ([Feedback and alerts](/architecture/interfaces.md#feedback-and-alerts)), never the other
    family's, even though both routes serve `FeedbackCreate` as a parametrised generic
    component."""
    schema = app.openapi()
    operation = object_at(schema, "paths", path, "post")
    request_ref = value_at(
        operation, "requestBody", "content", "application/json", "schema", "$ref"
    )
    if not isinstance(request_ref, str):
        raise AssertionError("feedback request ref must be a string")
    request_name = request_ref.rsplit("/", 1)[-1]
    verdict = object_at(schema, "components", "schemas", request_name, "properties", "verdict")

    assert verdict == {"$ref": f"#/components/schemas/{verdict_enum.__name__}"}
    enum_values = value_at(schema, "components", "schemas", verdict_enum.__name__, "enum")
    assert enum_values == [member.value for member in verdict_enum]


def test_documented_closed_response_sets_are_enums(app: FastAPI) -> None:
    schemas = object_at(app.openapi(), "components", "schemas")

    assert value_at(schemas, "ImportRowResult", "properties", "outcome", "enum") == [
        "CREATED",
        "UPDATED",
        "POSSIBLE_DUPLICATE",
        "INVALID",
    ]
    assert object_at(schemas, "ScoreChange", "properties", "trigger") == {
        "$ref": "#/components/schemas/PipelineRunTrigger"
    }
    assert object_at(schemas, "AlertBandChange", "properties", "from") == {
        "$ref": "#/components/schemas/AccountScoreBand"
    }
    assert object_at(schemas, "AlertBandChange", "properties", "to") == {
        "$ref": "#/components/schemas/AccountScoreBand"
    }


def test_prospect_sort_is_the_documented_closed_set(app: FastAPI) -> None:
    values = value_at(
        app.openapi(), "paths", "/api/v1/services/{id}/prospects", "get", "parameters"
    )
    parameters = [as_object(value, "prospect parameter") for value in as_list(values, "parameters")]
    sort = next(parameter for parameter in parameters if parameter.get("name") == "sort")
    any_of = as_list(value_at(sort, "schema", "anyOf"), "sort.anyOf")
    value_schema = next(
        as_object(item, "sort schema")
        for item in any_of
        if "enum" in as_object(item, "sort schema")
    )

    assert value_schema["enum"] == ["priority", "intent", "fit", "name", "last_refreshed"]
