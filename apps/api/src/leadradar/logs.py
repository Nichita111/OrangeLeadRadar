"""JSON line logging for both processes ([N-12](/requirements/system.md)).

Every record of every logger becomes one JSON line on stdout, carrying `request_id` and
`run_id` when they are bound for the current context. Uvicorn's own access log is turned off,
and every existing logger (root, `uvicorn.*`, `alembic`, `sqlalchemy`) is routed through the
same formatter, so no handler configured elsewhere can emit a plain line.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Formats one log record as one JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id
        run_id = run_id_var.get()
        if run_id is not None:
            payload["run_id"] = run_id
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value
        if record.exc_info is not None:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_json_logging(level: str) -> None:
    """Formats every record of every logger as one JSON line on stdout.

    Removes every existing handler from the root and from the named loggers that FastAPI,
    uvicorn and Alembic configure on their own, so that a stray plain line cannot appear, and
    disables uvicorn's access log.
    """
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "alembic", "sqlalchemy"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(level)

    logging.getLogger("uvicorn.access").disabled = True
