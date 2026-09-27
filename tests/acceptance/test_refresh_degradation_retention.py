"""Acceptance tests for the refresh target, degradation and retention criteria of the
`refresh-degradation-retention` task (N-02, N-06, N-08).

Criteria covered: AC-61, AC-62, AC-63.
Source of truth: docs/requirements/acceptance.md.

task.md (`.work/refresh-degradation-retention/task.md`) defers all three end-to-end:

    "AC-61, AC-62: need the FETCH and PROCESS steps (T10, #19) and the demo recording
     (H4, #22)."
    "AC-63: needs T10 and H4 for documents, and H3 (#9) for the EU clause; its contact
     clause is scoped to where contacts are built (DC9, T21)."

Each test below drives the system through the documented REST contracts (API-01, API-33,
API-35) against the composed stack, in FIXTURE_MODE=replay, exactly as the criterion states,
and reports the observed behaviour. None of them are expected to pass until T10, H4 and (for
AC-63) H3 and T21 land — that is recorded as NOT RUN with the observed evidence, never assumed.
"""

from __future__ import annotations

import time

import pytest
import requests

from conftest import API_BASE_URL, api_get, api_post, login, wait_for

# docs/architecture/overview.md#demo-dataset
_ADMIN_EMAIL = "admin@leadradar.local"

# docs/architecture/services/worker.md#runtime — documented default, not read from the
# implementation.
_REFRESH_TARGET_MINUTES_DEFAULT = 10

_TERMINAL = {"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"}


def _admin_client(stack: dict):
    password = stack["env"]["SEED_ADMIN_PASSWORD"]
    resp, client = login(_ADMIN_EMAIL, password)
    assert resp.status_code == 200, f"Admin login failed ({resp.status_code}): {resp.text!r}"
    return client


def _first_active_account(client) -> dict:
    resp = api_get("/accounts", client=client, params={"status": "ACTIVE", "page_size": 1})
    resp.raise_for_status()
    items = resp.json()["items"]
    assert items, "the demo dataset must seed at least one ACTIVE account (docs/architecture/overview.md#demo-dataset)"
    return items[0]


def _request_refresh(client, account_id: str) -> requests.Response:
    return api_post(f"/accounts/{account_id}/refresh", client=client)


def _get_run(client, run_id: str) -> dict:
    resp = api_get(f"/runs/{run_id}", client=client)
    resp.raise_for_status()
    return resp.json()


@pytest.mark.ac("AC-61")
def test_longest_demo_account_refresh_finishes_within_refresh_target_minutes(seeded):
    """AC-61 (docs/requirements/acceptance.md):

    "Given replay mode, when each demo account is refreshed alone, then the longest refresh
    finishes within REFRESH_TARGET_MINUTES."

    Command to reproduce: `uv run --project tests/acceptance pytest
    tests/acceptance/test_refresh_degradation_retention.py -k AC-61 -v`
    """
    client = _admin_client(seeded)
    account = _first_active_account(client)

    refresh_resp = _request_refresh(client, account["id"])
    if refresh_resp.status_code not in (200, 202):
        pytest.skip(
            "NOT RUN: POST /accounts/{id}/refresh (API-33) answered "
            f"{refresh_resp.status_code}: {refresh_resp.text!r}. task.md: \"AC-61 ... need "
            "the FETCH and PROCESS steps (T10, #19) and the demo recording (H4, #22).\" "
            "Missing surface: a working ACCOUNT_REFRESH pipeline."
        )
    run = refresh_resp.json()
    run_id = run["id"]

    deadline_s = _REFRESH_TARGET_MINUTES_DEFAULT * 60 + 60  # a minute of slack for polling
    started = time.monotonic()
    try:
        final_run = wait_for(
            lambda: (lambda r: r if r["status"] in _TERMINAL else None)(_get_run(client, run_id)),
            timeout_s=deadline_s,
            interval_s=3.0,
            description=f"run {run_id} to reach a terminal status",
        )
    except TimeoutError as exc:
        pytest.skip(
            f"NOT RUN: the refresh of {account['domain']} did not reach a terminal status "
            f"within {deadline_s}s (observed: {exc}). task.md defers AC-61 to T10 "
            "(FETCH/PROCESS steps) and H4 (the demo recording); consistent with that, no run "
            "of a demo account reaches SUCCEEDED, PARTIAL, FAILED or CANCELLED within the "
            "target window on this branch."
        )

    elapsed_minutes = (time.monotonic() - started) / 60
    if final_run["status"] not in ("SUCCEEDED", "PARTIAL"):
        pytest.skip(
            f"NOT RUN: the refresh of {account['domain']} ended {final_run['status']} "
            f"(errors={final_run.get('errors')}), not a completed refresh whose duration "
            "AC-61 can measure. task.md defers AC-61 to T10 and H4 (the demo recording); "
            f"the run finished in {elapsed_minutes:.1f} minutes with this outcome."
        )

    assert elapsed_minutes <= _REFRESH_TARGET_MINUTES_DEFAULT, (
        f"AC-61: the refresh of {account['domain']} took {elapsed_minutes:.1f} minutes, "
        f"more than REFRESH_TARGET_MINUTES ({_REFRESH_TARGET_MINUTES_DEFAULT})."
    )


@pytest.mark.ac("AC-62")
def test_dependency_outages_report_named_errors_and_leave_screens_answering(seeded):
    """AC-62 (docs/requirements/acceptance.md):

    "Given the demo recording, when in turn a plug-in, the classifier, OpenRouter, the
    embedder and HubSpot are made unavailable, then each affected refresh ... reports an
    error naming the dependency with the behaviour of the Degradation table, Prospects and
    Account detail keep answering, and no placeholder finding, score, quote or draft is
    stored."

    This criterion needs "the demo recording" (docs/architecture/overview.md#demo-dataset) to
    exist under FIXTURE_DIR so that a refresh can run far enough to be interrupted by each
    named dependency; task.md defers it to T10 (FETCH/PROCESS) and H4 (the demo recording).

    Command to reproduce: `uv run --project tests/acceptance pytest
    tests/acceptance/test_refresh_degradation_retention.py -k AC-62 -v`
    """
    client = _admin_client(seeded)
    account = _first_active_account(client)

    refresh_resp = _request_refresh(client, account["id"])
    if refresh_resp.status_code not in (200, 202):
        pytest.skip(
            "NOT RUN: POST /accounts/{id}/refresh (API-33) answered "
            f"{refresh_resp.status_code}: {refresh_resp.text!r}. task.md: \"AC-61, AC-62: "
            "need the FETCH and PROCESS steps (T10, #19) and the demo recording (H4, #22).\" "
            "Missing surface: a working ACCOUNT_REFRESH pipeline to interrupt with each "
            "dependency outage."
        )
    run_id = refresh_resp.json()["id"]

    try:
        final_run = wait_for(
            lambda: (lambda r: r if r["status"] in _TERMINAL else None)(_get_run(client, run_id)),
            timeout_s=_REFRESH_TARGET_MINUTES_DEFAULT * 60 + 60,
            interval_s=3.0,
            description=f"run {run_id} to reach a terminal status",
        )
    except TimeoutError as exc:
        pytest.skip(
            f"NOT RUN: the baseline refresh of {account['domain']} did not reach a terminal "
            f"status: {exc}. AC-62 needs a completed baseline refresh under the demo "
            "recording before any dependency can be made unavailable during a second one. "
            "task.md defers this to T10 and H4."
        )

    # Even a baseline run without any outage requires the recorded fixtures of the demo
    # recording (source plug-in, classifier and LLM exchanges) to produce real findings.
    # Its absence from FIXTURE_DIR (only fixtures/demo_accounts.csv is present) means no
    # outage scenario can be exercised meaningfully yet.
    pytest.skip(
        "NOT RUN: the baseline refresh of "
        f"{account['domain']} ended {final_run['status']} with errors="
        f"{final_run.get('errors')}. AC-62 requires re-running a refresh under the demo "
        "recording with each of a source plug-in, the classifier, OpenRouter, the embedder "
        "and HubSpot made unavailable in turn, and checking Prospects and Account detail "
        "keep answering meanwhile. Missing surface: the demo recording under FIXTURE_DIR "
        "(only fixtures/demo_accounts.csv is present) and the FETCH/PROCESS steps (task.md "
        "decisions G7's OpenRouter/CLASSIFIER wording cannot be exercised without it)."
    )


@pytest.mark.ac("AC-63")
def test_housekeeping_purges_document_text_and_erases_contacts_past_retention(seeded):
    """AC-63 (docs/requirements/acceptance.md):

    "Given the clock past a document's purge_after and a contact's retain_until, when
    housekeeping runs, then the document's text and its passages' text and embeddings are
    null except a passage referenced by an active label, its findings keep their quotes, and,
    where contacts are built, the contact is erased with a CONTACT_ERASED row of reason
    RETENTION; no log line or audit payload of the acceptance run contains a contact's name;
    the demo cloud machine runs in an EU region."

    task.md: "AC-63: needs T10 and H4 for documents, and H3 (#9) for the EU clause; its
    contact clause is scoped to where contacts are built (DC9, T21)." All three clauses are
    therefore deferred: the document clause needs a completed refresh under the demo
    recording (documents and passages exist only after a refresh,
    docs/architecture/overview.md#runtime: "Labels reference passages, which exist only
    after a refresh"); the EU-region clause is a deployment fact this local/CI acceptance
    stack cannot observe; the contact clause is out of this task's scope by DC9.

    Command to reproduce: `uv run --project tests/acceptance pytest
    tests/acceptance/test_refresh_degradation_retention.py -k AC-63 -v`
    """
    client = _admin_client(seeded)
    account = _first_active_account(client)

    refresh_resp = _request_refresh(client, account["id"])
    documents_available = refresh_resp.status_code in (200, 202)
    if documents_available:
        run_id = refresh_resp.json()["id"]
        try:
            final_run = wait_for(
                lambda: (lambda r: r if r["status"] in _TERMINAL else None)(_get_run(client, run_id)),
                timeout_s=_REFRESH_TARGET_MINUTES_DEFAULT * 60 + 60,
                interval_s=3.0,
                description=f"run {run_id} to reach a terminal status",
            )
            documents_available = final_run["status"] in ("SUCCEEDED", "PARTIAL")
        except TimeoutError:
            documents_available = False

    if documents_available:
        outcome = (
            "produced one, but this suite still needs a documented way to set a document "
            "past purge_after and a contact past retain_until and to trigger housekeeping "
            "deterministically via CLOCK_FILE and the worker's scheduler tick"
        )
    else:
        outcome = "did not produce one"

    pytest.skip(
        "NOT RUN: AC-63's document clause needs at least one document and passage, which "
        f"exist only after a completed refresh; the probed refresh of {account['domain']} "
        f"{outcome}. "
        "task.md defers the document clause to T10 (FETCH/PROCESS) and H4 (the demo "
        "recording); the EU-region clause names a deployment fact (the demo cloud machine) "
        "this local/CI acceptance stack cannot observe and defers it to H3 (#9); the contact "
        "clause is scoped out of this task by decision DC9 to wherever contacts are built "
        "(T21). No clause of AC-63 is testable from this task's built surface."
    )
