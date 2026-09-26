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
    env.setdefault("APP_DB_PASSWORD", "qa-app-" + uuid.uuid4().hex)
    # A key that is present but not a real secret: replay mode never calls out with it
    # (docs/architecture/interfaces.md#audit-and-health-shapes).
    env.setdefault("OPENROUTER_API_KEY", "qa-fake-key-" + uuid.uuid4().hex)
    env.setdefault("LLM_CLASSIFIER_MODEL", "openai/gpt-4o-mini")
    env.setdefault("LLM_EVIDENCE_MODEL", "openai/gpt-4o-mini")
    env.setdefault("LLM_OUTREACH_MODEL", "openai/gpt-4o-mini")
    # The demo users' passwords (docs/architecture/overview.md#demo-dataset), read by
    # `make seed-demo` (docs/architecture/services/api.md#runtime): at least
    # `PASSWORD_MIN_LENGTH` characters, never a real secret.
    env.setdefault("SEED_ADMIN_PASSWORD", "qa-admin-pw-" + uuid.uuid4().hex)
    env.setdefault("SEED_SALES_PASSWORD", "qa-sales-pw-" + uuid.uuid4().hex)
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
    try:
        # `--build`: `docker compose up` reuses an already-tagged image for this project name
        # without checking whether the source changed, so a project name reused across runs
        # (as every module-scoped project here is, run after run) would otherwise silently test
        # a stale build instead of the current code.
        compose(project, "up", "-d", "--build", "db", "api", "worker", "web", env=env)
        wait_for(
            lambda: requests.get(f"{API_BASE_URL}/health", timeout=5).status_code in (200, 503),
            timeout_s=180,
            description="the api to answer /health",
        )
        yield {"project": project, "base_url": API_BASE_URL, "env": env}
    finally:
        # Torn down even when `up` itself failed (e.g. a port left bound by an earlier run), so
        # a broken start never leaks containers, volumes or the `web` port into the next run.
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


class AuthedClient:
    """A signed-in caller, holding the `leadradar_session` cookie value `API-01` issued
    (docs/architecture/interfaces.md#conventions).

    The cookie is `Secure` (per `S-SEC-01`/`AC-52`), so a standards-following HTTP client -
    `requests` included - never re-attaches it to a request made over plain HTTP, which is all
    the composed stack offers locally (`web` on `http://localhost:8080`, no TLS in
    docs/architecture/overview.md#runtime). That is the browser's own transport rule, not
    something this product's routes decide, so it is worked around here by sending the cookie
    value as a literal `Cookie` header instead of through a cookie jar - exercising exactly the
    server-side authentication and revocation behaviour the acceptance criteria state, over the
    transport the harness actually has."""

    def __init__(self, cookie_value: str):
        self.cookie_value = cookie_value

    def _headers(self, given: dict | None) -> dict:
        headers = dict(given or {})
        headers["Cookie"] = f"leadradar_session={self.cookie_value}"
        return headers

    def get(self, url: str, **kwargs) -> requests.Response:
        headers = self._headers(kwargs.pop("headers", None))
        return requests.get(url, timeout=kwargs.pop("timeout", 10), headers=headers, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        headers = self._headers(kwargs.pop("headers", None))
        return requests.post(url, timeout=kwargs.pop("timeout", 10), headers=headers, **kwargs)

    def patch(self, url: str, **kwargs) -> requests.Response:
        headers = self._headers(kwargs.pop("headers", None))
        return requests.patch(url, timeout=kwargs.pop("timeout", 10), headers=headers, **kwargs)


def api_get(path: str, client: AuthedClient | None = None, **kwargs) -> requests.Response:
    caller = client.get if client is not None else requests.get
    return caller(f"{API_BASE_URL}{path}", timeout=10, **kwargs)


CSRF_HEADER = {"X-Requested-With": "XMLHttpRequest"}


def api_post(path: str, client: AuthedClient | None = None, csrf: bool = True, **kwargs) -> requests.Response:
    """A POST against the composed stack; carries the `X-Requested-With` CSRF header
    (docs/architecture/interfaces.md#conventions) unless `csrf=False`, so a test that means to
    omit it does so explicitly."""
    caller = client.post if client is not None else requests.post
    headers = dict(kwargs.pop("headers", {}) or {})
    if csrf:
        headers.update(CSRF_HEADER)
    return caller(f"{API_BASE_URL}{path}", timeout=10, headers=headers, **kwargs)


def api_patch(path: str, client: AuthedClient | None = None, csrf: bool = True, **kwargs) -> requests.Response:
    caller = client.patch if client is not None else requests.patch
    headers = dict(kwargs.pop("headers", {}) or {})
    if csrf:
        headers.update(CSRF_HEADER)
    return caller(f"{API_BASE_URL}{path}", timeout=10, headers=headers, **kwargs)


def login(email: str, password: str) -> tuple[requests.Response, AuthedClient | None]:
    """Signs in through `API-01`, without a header the CSRF convention requires, and returns
    the raw response alongside an `AuthedClient` of the cookie it set (`None` on failure)."""
    response = api_post("/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        return response, None
    set_cookie = response.headers.get("Set-Cookie", "")
    marker = "leadradar_session="
    start = set_cookie.index(marker) + len(marker)
    end = set_cookie.index(";", start) if ";" in set_cookie[start:] else len(set_cookie)
    return response, AuthedClient(set_cookie[start:end])


@pytest.fixture(scope="module")
def seeded(stack) -> dict:
    """`make seed-demo` (docs/architecture/overview.md#runtime, docs/Makefile): loads the demo
    users (docs/architecture/overview.md#demo-dataset) into the fresh database `stack` gives
    this module. Only the acceptance surface (the CLI entry point Compose's Makefile target
    calls) is used; nothing here reads how it is implemented."""
    compose(stack["project"], "exec", "-T", "api", "leadradar-seed-demo", env=stack["env"])
    return stack


def psql(project: str, env: dict[str, str], user: str, password: str, sql: str) -> subprocess.CompletedProcess:
    """Runs one SQL statement against the running `db` container as `user`, through `psql`
    inside the container (docs/architecture/overview.md#runtime names the two database roles:
    the owner `leadradar`, and the application role `leadradar_app`)."""
    return compose(
        project, "exec", "-T",
        "-e", f"PGPASSWORD={password}",
        "db", "psql", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", "leadradar", "-Atc", sql,
        env=env, capture=True, check=False,
    )
