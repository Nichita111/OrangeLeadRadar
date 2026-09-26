"""Unit test guarding `ApiSettings`' defaults against [api Runtime](
/architecture/services/api.md#runtime): a changed default in one place and not the other is a
defect this catches (DRY guard)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from leadradar.settings import ApiSettings

pytestmark = pytest.mark.unit

_API_RUNTIME = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "services" / "api.md"

# The keys this test can compare: those the api's own Runtime table gives a literal default for,
# and that `ApiSettings` also models (some Runtime keys, such as `DATABASE_URL`, have no default
# to compare, and some `ApiSettings` fields, such as `embedder_url`, are documented in the
# worker's Runtime table instead).
_FIELD_BY_KEY = {
    "SESSION_TTL_HOURS": "session_ttl_hours",
    "LOGIN_MAX_FAILURES": "login_max_failures",
    "LOGIN_LOCK_MINUTES": "login_lock_minutes",
    "PASSWORD_MIN_LENGTH": "password_min_length",
    "HEALTH_TIMEOUT_MS": "health_timeout_ms",
    "LOG_LEVEL": "log_level",
}


def _runtime_table_defaults() -> dict[str, str]:
    text = _API_RUNTIME.read_text()
    section = text.split("## Runtime", 1)[1].split("\n## ", 1)[0]
    defaults: dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(r"^\|\s*`([A-Z0-9_]+)`\s*\|\s*`([^`]+)`\s*\|", line)
        if match:
            defaults[match.group(1)] = match.group(2)
    return defaults


def test_settings_defaults_equal_the_api_runtime_table() -> None:
    documented = _runtime_table_defaults()
    assert documented, "expected to parse at least one default of the api Runtime table"

    for key, field in _FIELD_BY_KEY.items():
        assert key in documented, f"{key} not found in the api Runtime table"
        default = ApiSettings.model_fields[field].default
        expected: object = int(documented[key]) if isinstance(default, int) else documented[key]
        assert default == expected, f"{field} default {default!r} != {key} {expected!r}"
