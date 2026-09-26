"""The clock both processes inject ([api Runtime](/architecture/services/api.md#runtime),
[worker Runtime](/architecture/services/worker.md#runtime), [Fixture mode]
(/architecture/overview.md#runtime)): the system clock, or the time in `CLOCK_FILE` re-read on
every call, when `FIXTURE_MODE` is `replay`. Top level, not `api/`, because the worker reads the
same key and the fact has one owner. A malformed or missing file raises: no fallback result
([coding](/guidelines/coding.md))."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def now(*, fixture_mode: str, clock_file: Path | None) -> datetime:
    """The current time in UTC. In `replay` with `clock_file` set, parses its ISO-8601 content
    on every call; otherwise the system clock."""
    if fixture_mode == "replay" and clock_file is not None:
        text = clock_file.read_text().strip()
        return datetime.fromisoformat(text).astimezone(UTC)
    return datetime.now(tz=UTC)
