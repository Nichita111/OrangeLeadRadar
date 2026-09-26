"""Contract tests of [api Design](/architecture/services/api.md#design) (Request identity) and
[Conventions](/architecture/interfaces.md#conventions) (the envelope)."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from fastapi import FastAPI

from leadradar.logs import configure_json_logging

pytestmark = pytest.mark.contract


async def test_every_response_carries_x_request_id(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from leadradar.audit.health import HealthCheckStatus, HealthResult, HealthStatus

    async def fake_read_health(*args: object, **kwargs: object) -> HealthResult:
        return HealthResult(
            status=HealthStatus.OK,
            checks={
                "database": HealthCheckStatus.OK,
                "embedder": HealthCheckStatus.OK,
                "classifier": HealthCheckStatus.OK,
                "llm": HealthCheckStatus.OK,
            },
        )

    monkeypatch.setattr("leadradar.api.audit_and_health.read_health", fake_read_health)

    response = await client.get("/api/v1/health")

    assert response.headers.get("x-request-id")


async def test_a_log_line_written_during_the_request_carries_its_request_id(
    app: FastAPI, client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_json_logging("INFO")

    async def logs_something() -> dict[str, str]:
        logging.getLogger("leadradar.api.test_route").info("handling the request")
        return {"ok": "true"}

    app.add_api_route("/api/v1/__logs", logs_something, methods=["GET"])

    response = await client.get("/api/v1/__logs")
    request_id = response.headers["x-request-id"]

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    matching = [line for line in lines if line.get("request_id") == request_id]
    assert matching, "expected at least one log line carrying the response's request id"


def _mock_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    from leadradar.audit.health import HealthCheckStatus, HealthResult, HealthStatus

    async def fake_read_health(*args: object, **kwargs: object) -> HealthResult:
        return HealthResult(
            status=HealthStatus.OK,
            checks={
                "database": HealthCheckStatus.OK,
                "embedder": HealthCheckStatus.OK,
                "classifier": HealthCheckStatus.OK,
                "llm": HealthCheckStatus.OK,
            },
        )

    monkeypatch.setattr("leadradar.api.audit_and_health.read_health", fake_read_health)


async def test_a_served_request_writes_exactly_one_request_line_with_its_fields(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _mock_healthy(monkeypatch)
    configure_json_logging("INFO")

    response = await client.get("/api/v1/health")
    request_id = response.headers["x-request-id"]

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    request_lines = [line for line in lines if line.get("path") == "/api/v1/health"]
    assert len(request_lines) == 1
    line = request_lines[0]
    assert line["method"] == "GET"
    assert line["status"] == response.status_code
    assert line["request_id"] == request_id
    assert isinstance(line["duration_ms"], int | float)
    assert line["duration_ms"] >= 0


async def test_two_requests_write_two_request_lines_with_different_request_ids(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _mock_healthy(monkeypatch)
    configure_json_logging("INFO")

    first = await client.get("/api/v1/health")
    first_lines = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    second = await client.get("/api/v1/health")
    second_lines = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]

    first_request_lines = [line for line in first_lines if line.get("path") == "/api/v1/health"]
    second_request_lines = [line for line in second_lines if line.get("path") == "/api/v1/health"]
    assert len(first_request_lines) == 1
    assert len(second_request_lines) == 1
    assert first_request_lines[0]["request_id"] == first.headers["x-request-id"]
    assert second_request_lines[0]["request_id"] == second.headers["x-request-id"]
    assert first_request_lines[0]["request_id"] != second_request_lines[0]["request_id"]


async def test_a_request_with_a_query_string_writes_a_request_line_without_it(
    app: FastAPI, client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_json_logging("INFO")

    async def echo() -> dict[str, str]:
        return {"ok": "true"}

    app.add_api_route("/api/v1/__query", echo, methods=["GET"])

    response = await client.get("/api/v1/__query?secret=topsecret")

    assert response.status_code == 200
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    # Only the lines the api itself writes are in scope; the test's own `httpx.AsyncClient`
    # logs its outgoing call (with the query string) on the unrelated "httpx" logger, sharing
    # this process's stdout only because it is the ASGI test transport.
    api_lines = [line for line in lines if line.get("logger", "").startswith("leadradar")]
    assert all("topsecret" not in json.dumps(line) for line in api_lines)
    request_lines = [line for line in api_lines if line.get("path") == "/api/v1/__query"]
    assert len(request_lines) == 1


async def test_an_unhandled_exception_answers_500_with_the_internal_envelope(
    app: FastAPI, client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_json_logging("INFO")

    async def boom() -> None:
        raise RuntimeError("boom")

    app.add_api_route("/api/v1/__boom", boom, methods=["GET"])

    response = await client.get("/api/v1/__boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL", "message": "An unexpected error occurred."}
    }

    request_id = response.headers["x-request-id"]
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert any(
        line.get("request_id") == request_id and "boom" in line.get("exc_info", "")
        for line in lines
    )
    request_lines = [line for line in lines if line.get("path") == "/api/v1/__boom"]
    assert len(request_lines) == 1
    assert request_lines[0]["method"] == "GET"
    assert request_lines[0]["status"] == 500
    assert request_lines[0]["request_id"] == request_id


async def test_an_unknown_path_answers_404_with_the_not_found_envelope(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_json_logging("INFO")

    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "The resource does not exist."}
    }

    request_id = response.headers["x-request-id"]
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    request_lines = [line for line in lines if line.get("path") == "/api/v1/does-not-exist"]
    assert len(request_lines) == 1
    assert request_lines[0]["method"] == "GET"
    assert request_lines[0]["status"] == 404
    assert request_lines[0]["request_id"] == request_id


async def test_a_non_404_http_exception_keeps_its_own_status_and_is_not_mapped_to_internal(
    client: httpx.AsyncClient,
) -> None:
    """ "No other codes are mapped yet" (design): a `405` stays a `405`, not `500 INTERNAL`."""
    response = await client.post("/api/v1/health")

    assert response.status_code == 405
    assert response.json() != {"error": {"code": "INTERNAL", "message": "Method Not Allowed"}}
