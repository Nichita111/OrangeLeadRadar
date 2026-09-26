"""Every REST contract declares exactly the query parameters of its
[interfaces](/architecture/interfaces.md) row, plus `page` and `page_size` on `Page<T>`
([Conventions](/architecture/interfaces.md#conventions))."""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI

from .interfaces_parsing import (
    ContractRow,
    as_list,
    as_object,
    object_at,
    parse_interfaces,
    rest_contracts,
    top_level_fields,
)

pytestmark = pytest.mark.contract

_QUERY_SECTION_RE = re.compile(r"query\s+(.+?)\s*→")
_QUERY_TOKEN_RE = re.compile(r"`([a-z_]+)(?:\[\])?`")
_RESPONSE_SHAPE_RE = re.compile(r"\[`(\w+)`\]\(#[\w-]+\)")

_, SHAPES = parse_interfaces()


def _is_paginated(row: ContractRow) -> bool:
    """`Page<T>` of [Conventions](/architecture/interfaces.md#conventions), or a named response
    shape whose own table lists `page` and `page_size` (`ProspectPage`)."""
    response = row.request_response.split("→", 1)[-1]
    if "Page<" in response:
        return True
    shape_match = _RESPONSE_SHAPE_RE.search(response)
    if shape_match and shape_match.group(1) in SHAPES:
        fields = top_level_fields(SHAPES, shape_match.group(1))
        return {"page", "page_size"} <= fields
    return False


def _expected_query_params(row: ContractRow) -> set[str]:
    names: set[str] = set()
    section_match = _QUERY_SECTION_RE.search(row.request_response)
    if section_match:
        names |= set(_QUERY_TOKEN_RE.findall(section_match.group(1)))
    if _is_paginated(row):
        names |= {"page", "page_size"}
    return names


def _declared_query_params(schema: dict[str, object], row: ContractRow) -> set[str]:
    operation = object_at(schema, "paths", f"/api/v1{row.path}", row.method.lower())
    names: set[str] = set()
    for value in as_list(operation.get("parameters", []), f"{row.id} parameters"):
        parameter = as_object(value, f"{row.id} parameter")
        if parameter.get("in") == "query":
            name = parameter.get("name")
            if not isinstance(name, str):
                raise AssertionError(f"{row.id} query parameter name must be a string")
            names.add(name)
    return names


@pytest.mark.parametrize("row", rest_contracts(), ids=lambda row: row.id)
def test_each_contract_declares_the_query_parameters_of_its_row(
    row: ContractRow, app: FastAPI
) -> None:
    schema = app.openapi()
    expected = _expected_query_params(row)
    declared = _declared_query_params(schema, row)
    assert expected == declared, f"{row.id}: expected {expected}, declared {declared}"
