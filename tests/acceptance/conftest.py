"""Acceptance test harness: brings up the composed stack of
docs/architecture/overview.md#runtime (docker compose up) and gives tests a base URL to the
API through the web container's proxy, exactly as the Runtime section describes it. Nothing
here is read from the implementation; the client shapes come from
docs/architecture/interfaces.md and the configuration keys from the services' Runtime
sections.

FIXTURE_MODE is replay and the clock is injected through CLOCK_FILE, per
docs/guidelines/testing.md#acceptance-tests. An OpenRouter key and model ids are supplied
(never a real one) so that, in replay mode, the classifier and llm health checks take the
"configured" branch and report FIXTURE_DIR's readability instead of calling out
(docs/architecture/interfaces.md#audit-and-health-shapes) - no test asserts on the value of
these settings themselves.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from collections.abc import Iterator

import pytest
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE_COMPOSE = os.path.join(ROOT, "compose.yaml")
OVERRIDE_COMPOSE = os.path.join(ROOT, "tests", "acceptance", "docker", "compose.override.yml")
WEB_PORT = 8080
API_BASE_URL = f"http://localhost:{WEB_PORT}/api/v1"


def _compose_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("POSTGRES_PASSWORD", "qa-" + uuid.uuid4().hex)
    # A key that is present but not a real secret: replay mode never calls out with it
    # (docs/architecture/interfaces.md#audit-and-health-shapes).
    env.setdefault("OPENROUTER_API_KEY", "qa-fake-key-" + uuid.uuid4().hex)
    env.setdefault("LLM_CLASSIFIER_MODEL", "openai/gpt-4o-mini")
    env.setdefault("LLM_EVIDENCE_MODEL", "openai/gpt-4o-mini")
    env.setdefault("LLM_OUTREACH_MODEL", "openai/gpt-4o-mini")
    return env


def compose(project: str, *args: str, env: dict[str, str] | None = None,
            check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = [
        "docker", "compose",
        "-p", project,
        "-f", BASE_COMPOSE,
        "-f", OVERRIDE_COMPOSE,
        *args,
    ]
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env or _compose_env(),
        check=check,
        capture_output=capture,
        text=True,
        timeout=600,
    )


def wait_for(predicate, timeout_s: float, interval_s: float = 2.0, description: str = "condition"):
    deadline = time.monotonic() + timeout_s
    last_exc = None
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except Exception as exc:
            # A predicate may raise for any reason while its condition is still pending
            # (connection refused, a non-JSON body); the loop keeps retrying and the last
            # such failure is reported if the timeout is reached.
            last_exc = exc
        time.sleep(interval_s)
    raise TimeoutError(f"timed out after {timeout_s}s waiting for {description}: {last_exc}")


@pytest.fixture(scope="module")
def stack(request) -> Iterator[dict]:
    """db, api, worker and web up, per docs/architecture/overview.md#runtime; a fresh
    database per test module (docs/guidelines/testing.md#test-independence)."""
    project = "lr-qa-" + request.module.__name__.rsplit(".", 1)[-1].replace("_", "-")
    env = _compose_env()
    compose(project, "up", "-d", "db", "api", "worker", "web", env=env)
    try:
        wait_for(
            lambda: requests.get(f"{API_BASE_URL}/health", timeout=5).status_code in (200, 503),
            timeout_s=180,
            description="the api to answer /health",
        )
        yield {"project": project, "base_url": API_BASE_URL, "env": env}
    finally:
        compose(project, "down", "-v", env=env, check=False)


def db_tables(project: str, env: dict[str, str]) -> set[str]:
    """The base tables of the `public` schema of the running `db` container, queried through
    `psql` (the credentials of compose.yaml's `db` service: user and database `leadradar`) -
    used to check "the migrations are applied" against the table headings of
    docs/architecture/sql-store.md."""
    result = compose(
        project, "exec", "-T", "db",
        "psql", "-U", "leadradar", "-d", "leadradar", "-Atc",
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public';",
        env=env, capture=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def api_get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{API_BASE_URL}{path}", timeout=10, **kwargs)
