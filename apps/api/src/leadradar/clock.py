"""The clock of the api, the worker and the AI gateway
([worker Runtime](/architecture/services/worker.md#runtime) `CLOCK_FILE`): the system UTC clock,
or, in fixture record or replay, the time a file names, read on every call so recording, replay
and the acceptance tests can advance it between requests. Pacing always measures real time
(`worker/steps/fetch.py` gives the crawl client the system clock), so this only ever governs fetch
windows, stored times and decay."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from leadradar.ai.settings import AiGatewaySettings


def build_clock(settings: AiGatewaySettings) -> Callable[[], datetime]:
    """`CLOCK_FILE` is honoured when `FIXTURE_MODE` is `record` or `replay`; unset or `off` uses
    the system clock."""
    if settings.fixture_mode in ("record", "replay") and settings.clock_file is not None:
        clock_file = settings.clock_file

        def _read_clock_file() -> datetime:
            return datetime.fromisoformat(clock_file.read_text().strip())

        return _read_clock_file

    def _system_clock() -> datetime:
        return datetime.now(tz=UTC)

    return _system_clock
