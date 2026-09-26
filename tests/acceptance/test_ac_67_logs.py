"""AC-67 (docs/requirements/acceptance.md):
"Given the logs of the `api` and `worker` containers after the acceptance run, when they are
scanned, then every line is JSON, every line written while serving a request carries its
`request_id` and every line written for a run its `run_id`, and none contains a password, a
session token or an API key."

The `run_id` half is deferred by `.work/auth-and-audit/task.md`, carried over from
`stack-foundation`: no run exists until the worker's job loop lands with `S-PIP-01`; it is
verified by the task that implements it.

Sign-in (`API-01`, `/auth/login`) is built by this task
(docs/architecture/interfaces.md#authentication-and-users-contracts), seeded by
`make seed-demo` (docs/architecture/overview.md#demo-dataset), so this test now signs in with
both a wrong and the right password for the seeded Sales user and checks that neither the
submitted password nor the session cookie's token ever appears in a log line. The
`POSTGRES_PASSWORD` the harness sets reaches both containers through `DATABASE_URL`, which the
Compose file builds from it (docs/architecture/services/api.md#runtime; the worker reuses the
api's `DATABASE_URL` per its own Runtime section) - so this test asserts that value appears in
no log line too.

"A line written while serving a request" is identified without guessing at the log line's
shape: "Request identity" (docs/architecture/services/api.md#design) says every request gets a
request id, "returned in the X-Request-Id header, written to every log line ... of the
request" - so the X-Request-Id header of a served request (`API-61`, the only route that needs
no session) is the request_id at least one log line of that request must carry.
"""

from __future__ import annotations

import json

import pytest

from conftest import api_get, api_post, compose, login

SALES_EMAIL = "sales@leadradar.local"


@pytest.mark.ac("AC-67")
def test_api_and_worker_logs_are_json_and_carry_the_served_requests_request_id(seeded):
    project = seeded["project"]
    env = seeded["env"]
    sales_password = env["SEED_SALES_PASSWORD"]

    health_response = api_get("/health")
    assert health_response.status_code in (200, 503)
    request_id = health_response.headers.get("X-Request-Id")
    assert request_id, "API-61 must return an X-Request-Id header (Request identity)"

    # A wrong-password and then a right-password sign-in, so a submitted password and an issued
    # session token both exist in the api's activity before the logs are scanned.
    wrong_login = api_post("/auth/login", json={"email": SALES_EMAIL, "password": "not-the-password"})
    assert wrong_login.status_code == 401, wrong_login.text

    right_login_response, client = login(SALES_EMAIL, sales_password)
    assert right_login_response.status_code == 200, right_login_response.text
    assert client is not None
    session_token = client.cookie_value

    logs = compose(
        project, "logs", "--no-color", "--no-log-prefix", "api", "worker",
        env=env, capture=True, check=False,
    ).stdout
    lines = [line for line in logs.splitlines() if line.strip()]
    assert lines, "expected at least one log line from the api and worker containers"

    # "every line is JSON"
    parsed_lines = []
    for line in lines:
        try:
            parsed_lines.append(json.loads(line))
        except json.JSONDecodeError as exc:
            pytest.fail(f"a log line of api/worker is not JSON: {line!r} ({exc})")

    # "every line written while serving a request carries its request_id" - the served
    # /health request's own log line(s) must carry the request_id its response named.
    matching = [entry for entry in parsed_lines if entry.get("request_id") == request_id]
    assert matching, (
        f"expected a log line carrying request_id {request_id!r}, the X-Request-Id header "
        f"API-61 returned for the served request"
    )

    # "none contains a password" - POSTGRES_PASSWORD reaches both api and worker through
    # DATABASE_URL (api Runtime; the worker reuses the api's DATABASE_URL), and the wrong and
    # right passwords were just submitted to /auth/login.
    for secret in (env["POSTGRES_PASSWORD"], sales_password, "not-the-password"):
        for line in lines:
            assert secret not in line, f"log line leaks a password ({secret!r}): {line!r}"

    # "none contains ... a session token" - the cookie value just issued by the right sign-in.
    for line in lines:
        assert session_token not in line, f"log line leaks the session token: {line!r}"

    # "none contains ... an API key" - the key the acceptance harness configures
    # (docs/architecture/interfaces.md#audit-and-health-shapes); never a real one.
    api_key = env["OPENROUTER_API_KEY"]
    for line in lines:
        assert api_key not in line, f"log line leaks the configured API key: {line!r}"
