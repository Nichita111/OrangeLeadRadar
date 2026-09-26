"""AC-67 (docs/requirements/acceptance.md):
"Given the logs of the `api` and `worker` containers after the acceptance run, when they are
scanned, then every line is JSON, every line written while serving a request carries its
`request_id` and every line written for a run its `run_id`, and none contains a password, a
session token or an API key."

The `run_id` half is deferred (`.work/stack-foundation/task.md`): no run exists until the
worker's job loop lands with `S-PIP-01`.

Sign-in (`API-01`, `/auth/login`) is not built in this task (`.work/stack-foundation/task.md`),
so this test never calls it; without it, no password ever reaches the api and no session token
is ever created, so this test cannot exercise those two halves of "none contains a password, a
session token or an API key" - only the API-key half is covered, with the key the acceptance
harness configures.

"A line written while serving a request" is identified without guessing at the log line's
shape: "Request identity" (docs/architecture/services/api.md#design) says every request gets a
request id, "returned in the X-Request-Id header, written to every log line ... of the
request" - so the X-Request-Id header of a served request (`API-61`, the only route that needs
no session) is the request_id at least one log line of that request must carry.
"""

from __future__ import annotations

import json

import pytest

from conftest import api_get, compose


@pytest.mark.ac("AC-67")
def test_api_and_worker_logs_are_json_and_carry_the_served_requests_request_id(stack):
    project = stack["project"]
    env = stack["env"]

    health_response = api_get("/health")
    assert health_response.status_code in (200, 503)
    request_id = health_response.headers.get("X-Request-Id")
    assert request_id, "API-61 must return an X-Request-Id header (Request identity)"

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

    # "none contains ... an API key" - the key the acceptance harness configures
    # (docs/architecture/interfaces.md#audit-and-health-shapes); never a real one.
    api_key = env["OPENROUTER_API_KEY"]
    for line in lines:
        assert api_key not in line, f"log line leaks the configured API key: {line!r}"
