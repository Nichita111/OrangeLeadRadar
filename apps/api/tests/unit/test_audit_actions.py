"""Unit test guarding the one definition of [Audit actions](
/architecture/sql-store.md#audit-actions): `AuditAction` and `AUDIT_ACTION_KIND` must equal the
document's table exactly (DRY guard, [S-AUD-01](/requirements/system.md))."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from leadradar.core.enums import AUDIT_ACTION_KIND, AuditAction, AuditEventKind

pytestmark = pytest.mark.unit

_DOCS_ROOT = Path(__file__).resolve().parents[4] / "docs"
_SQL_STORE = _DOCS_ROOT / "architecture" / "sql-store.md"


def _audit_actions_table() -> dict[str, str]:
    """Parses the `Action | Kind | Entity | Payload` rows under `## Audit actions`."""
    text = _SQL_STORE.read_text()
    section = text.split("## Audit actions", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(r"^\|\s*`([A-Z_]+)`\s*\|\s*`([A-Z_]+)`\s*\|", line)
        if match:
            rows[match.group(1)] = match.group(2)
    return rows


def test_audit_actions_and_their_kinds_equal_the_audit_actions_table() -> None:
    documented = _audit_actions_table()
    assert documented, "expected to parse at least one row of the Audit actions table"

    assert {action.value for action in AuditAction} == set(documented)
    for action, kind in documented.items():
        assert AUDIT_ACTION_KIND[AuditAction(action)] == AuditEventKind(kind)
