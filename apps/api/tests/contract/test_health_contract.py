"""Contract tests of `API-61` `GET /api/v1/health`
([Audit and health](/architecture/interfaces.md#audit-and-health))."""

from __future__ import annotations

import httpx
import pytest

from leadradar.audit.health import HealthCheckStatus, HealthResult, HealthStatus

pytestmark = pytest.mark.contract


async def test_health_answers_200_with_exactly_status_and_checks(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"status", "checks"}
    assert set(body["checks"].keys()) == {"database", "embedder", "classifier", "llm"}
    assert body["status"] in {"OK", "DEGRADED", "DOWN"}
    for value in body["checks"].values():
        assert value in {"OK", "DOWN", "NOT_CONFIGURED"}


async def test_health_answers_503_with_status_down_when_the_database_check_fails(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_read_health(*args: object, **kwargs: object) -> HealthResult:
        return HealthResult(
            status=HealthStatus.DOWN,
            checks={
                "database": HealthCheckStatus.DOWN,
                "embedder": HealthCheckStatus.OK,
                "classifier": HealthCheckStatus.OK,
                "llm": HealthCheckStatus.OK,
            },
        )

    monkeypatch.setattr("leadradar.api.audit_and_health.read_health", fake_read_health)

    response = await client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["status"] == "DOWN"
