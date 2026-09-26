"""[Conventions](/architecture/interfaces.md#conventions) `VALIDATION`: a `RequestValidationError`
location becomes the `field` of `details.fields[]`, a body field name or a JSON pointer."""

from __future__ import annotations

import pytest

from leadradar.api.errors import _field_from_location

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("location", "field"),
    [
        (("body", "name"), "name"),
        (("body", 0), "/0"),
        (("body", "a", 0, "b"), "/a/0/b"),
        (("body",), "/"),
    ],
)
def test_a_validation_error_location_becomes_a_json_pointer_field(
    location: tuple[int | str, ...], field: str
) -> None:
    assert _field_from_location(location) == field
