"""AC-57 (docs/requirements/acceptance.md):
"Given a machine with Docker and no database, when `docker compose up` runs, then `web`,
`api`, `worker`, `db` and `embedder` start, the migrations are applied, `/health` answers `OK`
with every check reported, and with the embedder stopped it answers `DEGRADED` naming
`embedder`."

Driven only through `GET /health` (`API-61`,
docs/architecture/interfaces.md#audit-and-health-contracts) and the state of the composed
stack (docs/architecture/overview.md#runtime); nothing here reads the implementation.
"""

from __future__ import annotations

import json

import pytest
import requests

from conftest import API_BASE_URL, _compose_env, compose, wait_for

PROJECT = "lr-qa-ac-57"


@pytest.fixture(scope="module")
def full_stack():
    """The whole Runtime table (docs/architecture/overview.md#runtime): web, api, worker, db
    and embedder, starting from no database (a fresh named volume)."""
    env = _compose_env()
    compose(PROJECT, "up", "-d", "db", "api", "worker", "web", "embedder", env=env, check=False)
    try:
        yield {"env": env}
    finally:
        compose(PROJECT, "down", "-v", env=env, check=False)


def _running_services(env: dict[str, str]) -> set[str]:
    result = compose(PROJECT, "ps", "--format", "json", env=env, capture=True, check=False)
    names = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if entry.get("State") == "running":
            names.add(entry.get("Service"))
    return names


@pytest.mark.ac("AC-57")
def test_compose_up_starts_every_container_migrates_and_health_reports_ok_then_degraded_without_embedder(
    full_stack,
):
    env = full_stack["env"]

    # "web, api, worker, db and embedder start"
    running = wait_for(
        lambda: _running_services(env) if {"web", "api", "worker", "db", "embedder"} <= _running_services(env) else None,
        timeout_s=1200,
        interval_s=5.0,
        description="web, api, worker, db and embedder to be running",
    )
    assert {"web", "api", "worker", "db", "embedder"} <= running

    # "the migrations are applied, /health answers OK with every check reported"
    health = wait_for(
        lambda: (lambda r: r.json() if r.status_code == 200 and r.json().get("status") == "OK" else None)(
            requests.get(f"{API_BASE_URL}/health", timeout=10)
        ),
        timeout_s=1200,
        interval_s=5.0,
        description="/health to answer OK with every check reported",
    )
    assert health["status"] == "OK"
    assert set(health["checks"]) == {"database", "embedder", "classifier", "llm"}
    assert all(value == "OK" for value in health["checks"].values()), health["checks"]

    # "with the embedder stopped it answers DEGRADED naming embedder"
    compose(PROJECT, "stop", "embedder", env=env)
    degraded = wait_for(
        lambda: (lambda r: r.json() if r.status_code == 200 and r.json().get("status") == "DEGRADED" else None)(
            requests.get(f"{API_BASE_URL}/health", timeout=10)
        ),
        timeout_s=60,
        interval_s=2.0,
        description="/health to answer DEGRADED naming embedder",
    )
    assert degraded["status"] == "DEGRADED"
    assert degraded["checks"]["embedder"] != "OK"
    assert degraded["checks"]["database"] == "OK"
