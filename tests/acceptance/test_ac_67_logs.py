"""AC-67 (docs/requirements/acceptance.md):
"Given the logs of the `api` and `worker` containers after the acceptance run, when they are
scanned, then every line is JSON, every line written while serving a request carries its
`request_id` and every line written for a run its `run_id`, and none contains a password, a
session token or an API key."

The `run_id` half is deferred (`.work/stack-foundation/task.md`): no run exists until the
worker's job loop lands with `S-PIP-01`. This test covers: every line of both containers is
JSON; every line written while serving a request carries its `request_id`; no line contains
the password sent to `/auth/login` or the configured `OPENROUTER_API_KEY`.
"""

from __future__ import annotations

import json

import pytest

from conftest import api_get, api_post, compose

PASSWORD = "correct horse battery staple, not a real password"  # noqa: S105 - a probe value, never a real secret


@pytest.mark.ac("AC-67")
def test_api_and_worker_logs_are_json_carry_request_id_and_contain_no_secret(stack):
    project = stack["project"]
    env = stack["env"]

    # Two served requests, so the logs contain lines written while serving a request: one
    # anonymous (`API-61`) and one that carries a password (`API-01`).
    health_response = api_get("/health")
    assert health_response.status_code in (200, 503)
    login_response = api_post(
        "/auth/login",
        json={"email": "nobody@example.invalid", "password": PASSWORD},
    )
    assert login_response.status_code in (200, 401, 403, 423, 422)

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

    # "every line written while serving a request carries its request_id" - lines naming
    # either served request's path are lines written while serving it.
    request_lines = [
        (line, entry) for line, entry in zip(lines, parsed_lines, strict=True)
        if "/health" in line or "/auth/login" in line
    ]
    assert request_lines, "expected log lines written while serving /health or /auth/login"
    for line, entry in request_lines:
        assert entry.get("request_id"), f"line written while serving a request has no request_id: {line!r}"

    # "none contains a password, a session token or an API key"
    secrets = [PASSWORD, env["OPENROUTER_API_KEY"]]
    session_cookie = login_response.cookies.get("session") or next(
        iter(login_response.cookies.values()), None
    )
    if session_cookie:
        secrets.append(session_cookie)
    for line in lines:
        for secret in secrets:
            assert secret not in line, f"log line leaks a secret: {line!r}"
