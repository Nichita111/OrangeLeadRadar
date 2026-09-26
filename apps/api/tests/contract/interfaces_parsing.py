"""Parses [interfaces](/architecture/interfaces.md) for the contract tests: every REST contract
row (method, path) and every named shape's top-level field names, expanding "every field of X"
and comma-separated names. Not a test module itself; imported by the ones that read it.

Fails loudly (an assertion or a `KeyError`) on a row it cannot read, rather than skipping it,
as [the design](/.work/frontend-foundation/design.md) requires."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

INTERFACES_PATH = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "interfaces.md"

_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

_CONTRACT_ROW_RE = re.compile(
    r"^\|\s*`(API-\d+)`\s*\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$"
)
_SHAPE_HEADING_RE = re.compile(r"^#### (\w+)$")
_EVERY_FIELD_RE = re.compile(r"every field of \[`(\w+)`\]\(#[\w-]+\)(?: except `([a-z_]+)`)?")
_FIELD_TOKEN_RE = re.compile(r"`([a-z][a-z0-9_]*)`")


@dataclass(frozen=True)
class ContractRow:
    """One row of a REST contracts table."""

    id: str
    method: str
    path: str
    roles: str
    request_response: str


def as_object(value: object, context: str) -> dict[str, object]:
    """Narrows parsed OpenAPI JSON only after checking its object shape."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise AssertionError(f"{context} must be an object")
    return cast(dict[str, object], value)


def as_list(value: object, context: str) -> list[object]:
    """Narrows parsed OpenAPI JSON only after checking its array shape."""
    if not isinstance(value, list):
        raise AssertionError(f"{context} must be an array")
    return cast(list[object], value)


def value_at(value: object, *keys: str) -> object:
    """Reads a checked path through parsed OpenAPI objects."""
    current = value
    for key in keys:
        current = as_object(current, ".".join(keys))[key]
    return current


def object_at(value: object, *keys: str) -> dict[str, object]:
    return as_object(value_at(value, *keys), ".".join(keys))


def _is_separator_row(line: str) -> bool:
    return set(line.replace("|", "").replace("-", "").replace(":", "").strip()) == set()


def parse_interfaces() -> tuple[list[ContractRow], dict[str, list[str]]]:
    """Every REST contract row, in document order, and every named shape's raw Field-column
    cells (not yet expanded)."""
    lines = INTERFACES_PATH.read_text().splitlines()
    contracts: list[ContractRow] = []
    shapes: dict[str, list[str]] = {}
    current_shape: str | None = None

    for line in lines:
        heading_match = _SHAPE_HEADING_RE.match(line)
        if heading_match:
            current_shape = heading_match.group(1)
            shapes[current_shape] = []
            continue
        if line.startswith("## ") or line.startswith("### "):
            current_shape = None
            continue

        contract_match = _CONTRACT_ROW_RE.match(line)
        if contract_match:
            id_, method, path, roles, request_response = contract_match.groups()
            contracts.append(ContractRow(id_, method, path.strip("`"), roles, request_response))
            continue

        if (
            current_shape is not None
            and line.strip().startswith("|")
            and not _is_separator_row(line)
        ):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            field_cell = cells[0] if cells else ""
            if field_cell in {"Field", "Column", ""}:
                continue
            shapes[current_shape].append(field_cell)

    assert contracts, "expected at least one REST contract row"
    assert shapes, "expected at least one shape"
    return contracts, shapes


def rest_contracts() -> list[ContractRow]:
    """Every REST contract: a Method that is an HTTP verb, per the design's
    `test_every_rest_contract_of_interfaces_is_a_route_with_its_method_and_path`."""
    contracts, _ = parse_interfaces()
    return [row for row in contracts if row.method in _HTTP_METHODS]


def top_level_fields(
    shapes: dict[str, list[str]], name: str, _seen: frozenset[str] = frozenset()
) -> set[str]:
    """The top-level field names of a named shape, expanding "every field of X [except y]" and
    skipping rows that describe a nested array item's own fields (`x[].y`)."""
    if name in _seen:
        raise AssertionError(f"cyclic 'every field of' chain reaches {name} again")
    if name not in shapes:
        raise KeyError(f"interfaces.md has no shape heading '#### {name}'")
    seen = _seen | {name}
    fields: set[str] = set()
    for cell in shapes[name]:
        if "[]." in cell:
            continue
        every_match = _EVERY_FIELD_RE.search(cell)
        if every_match:
            base_name, excluded = every_match.groups()
            base_fields = top_level_fields(shapes, base_name, seen)
            fields |= base_fields - ({excluded} if excluded else set())
            continue
        tokens = _FIELD_TOKEN_RE.findall(cell)
        if not tokens:
            raise AssertionError(f"cannot read the Field cell {cell!r} of shape {name!r}")
        fields |= set(tokens)
    return fields
