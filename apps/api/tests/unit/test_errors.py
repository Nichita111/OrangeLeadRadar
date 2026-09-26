"""[Conventions](/architecture/interfaces.md#conventions) `VALIDATION`: a `RequestValidationError`
location becomes the `field` of `details.fields[]` — a body field name, a JSON pointer into it, or
the name of a path or query parameter."""

from __future__ import annotations

import pytest

from leadradar.api.errors import _field_name

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("location", "field"),
    [
        (("body", "name"), "name"),
        (("body", "a", 0, "b"), "/a/0/b"),
        (("body", 0), "/0"),
        (("body",), "/"),
        (("path", "id"), "id"),
        (("query", "page_size"), "page_size"),
    ],
)
def test_a_validation_error_location_becomes_a_json_pointer_field(
    location: tuple[int | str, ...], field: str
) -> None:
    assert _field_name(location) == field
