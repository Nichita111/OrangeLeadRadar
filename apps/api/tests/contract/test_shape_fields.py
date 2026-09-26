"""Every named shape of [interfaces](/architecture/interfaces.md) that a REST contract uses has
exactly the fields of its table: comma-separated names and "every field of" expanded, equal to
the OpenAPI component's own properties."""

from __future__ import annotations

import re

import pytest
from pydantic import SecretStr

from leadradar.api.app import create_app
from leadradar.settings import ApiSettings

from .interfaces_parsing import (
    generic_base_name,
    parse_interfaces,
    rest_contracts,
    top_level_fields,
)

pytestmark = pytest.mark.contract

_, SHAPES = parse_interfaces()

# Named shapes that a REST route's request or response links directly (not a nested anonymous
# object, and not a shape of the in-process families, which this task does not build routes for).
# `AccountImportRow` (`API-22`) names a CSV row's columns, not a JSON request or response body,
# so it has no OpenAPI component to compare against.
_ROUTE_LINKED_NAMES = {
    name
    for row in rest_contracts()
    for name in re.findall(r"\[`(\w+)`\]\(#[\w-]+\)", row.request_response)
} - {"AccountImportRow"}

_SETTINGS = ApiSettings(database_url=SecretStr("postgresql://u:p@localhost/db"))
_COMPONENTS = create_app(_SETTINGS).openapi()["components"]["schemas"]


def _instantiations_of(name: str) -> list[str]:
    """Component names whose `title` is `name[...]` — a parametrised generic instantiation of
    the shape `name`, e.g. `FeedbackCreate_LeadFeedbackVerdict_` (title
    `FeedbackCreate[LeadFeedbackVerdict]`) for `FeedbackCreate`."""
    return [
        component_name
        for component_name, component in _COMPONENTS.items()
        if generic_base_name(component.get("title"), {name}) == name
    ]


@pytest.mark.parametrize("name", sorted(_ROUTE_LINKED_NAMES), ids=lambda name: name)
def test_each_shape_has_exactly_the_fields_of_its_interfaces_table(name: str) -> None:
    expected = top_level_fields(SHAPES, name)
    component_names = [name] if name in _COMPONENTS else _instantiations_of(name)
    if not component_names:
        pytest.fail(f"no component schema named {name!r} for a shape a route links")
    for component_name in component_names:
        actual = set(_COMPONENTS[component_name].get("properties", {}).keys())
        assert expected == actual, (
            f"{name} ({component_name}): doc has {expected}, component has {actual}"
        )
