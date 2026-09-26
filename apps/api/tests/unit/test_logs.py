"""Unit tests of [`logs.py`](/guidelines/python.md#style): every record of every logger becomes
one JSON line, carrying `request_id` and `run_id` when bound ([N-12](/requirements/system.md))."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from leadradar.logs import configure_json_logging, request_id_var, run_id_var

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_context_vars() -> Iterator[None]:
    request_token = request_id_var.set(None)
    run_token = run_id_var.set(None)
    yield
    request_id_var.reset(request_token)
    run_id_var.reset(run_token)


def test_every_log_record_is_one_json_line(capsys: pytest.CaptureFixture[str]) -> None:
    configure_json_logging("INFO")
    logging.getLogger("uvicorn.error").info("hello")

    line = capsys.readouterr().out.strip()
    record = json.loads(line)
    assert record["message"] == "hello"
    assert "request_id" not in record
    assert "run_id" not in record


def test_a_line_written_while_serving_a_request_carries_request_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_json_logging("INFO")
    token = request_id_var.set("req-123")
    try:
        logging.getLogger("leadradar.api").info("serving")
    finally:
        request_id_var.reset(token)

    record = json.loads(capsys.readouterr().out.strip())
    assert record["request_id"] == "req-123"
    assert "run_id" not in record


def test_a_line_written_for_a_run_carries_run_id(capsys: pytest.CaptureFixture[str]) -> None:
    configure_json_logging("INFO")
    token = run_id_var.set("run-456")
    try:
        logging.getLogger("leadradar.worker").info("running a job")
    finally:
        run_id_var.reset(token)

    record = json.loads(capsys.readouterr().out.strip())
    assert record["run_id"] == "run-456"
    assert "request_id" not in record


def test_a_process_level_line_carries_neither_id(capsys: pytest.CaptureFixture[str]) -> None:
    configure_json_logging("INFO")
    logging.getLogger("leadradar.worker").info("worker started")

    record = json.loads(capsys.readouterr().out.strip())
    assert "request_id" not in record
    assert "run_id" not in record


def test_the_uvicorn_access_logger_writes_no_line_once_configured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_json_logging("INFO")
    logging.getLogger("uvicorn.access").info('127.0.0.1:0 - "GET / HTTP/1.1" 200')

    assert capsys.readouterr().out == ""


def test_an_exception_log_line_is_still_one_json_line_with_the_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_json_logging("INFO")
    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("leadradar.api").exception("failed")

    line = capsys.readouterr().out.strip()
    assert "\n" not in line
    record = json.loads(line)
    assert "ValueError: boom" in record["exc_info"]
