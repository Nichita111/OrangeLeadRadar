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


async def test_an_unknown_path_answers_404_with_the_not_found_envelope(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "The resource does not exist."}
    }


async def test_a_non_404_http_exception_keeps_its_own_status_and_is_not_mapped_to_internal(
    client: httpx.AsyncClient,
) -> None:
    """ "No other codes are mapped yet" (design): a `405` stays a `405`, not `500 INTERNAL`."""
    response = await client.post("/api/v1/health")

    assert response.status_code == 405
    assert response.json() != {"error": {"code": "INTERNAL", "message": "Method Not Allowed"}}
