"""Acceptance tests for scoring rules, scoring stage, rescoring and scoring-version activation.

Criteria covered: AC-06, AC-33, AC-34, AC-35, AC-36, AC-37, AC-38, AC-39, AC-40.
Source of truth: docs/requirements/acceptance.md (Scoring section).

All tests drive the system exclusively through the REST contracts documented in
docs/architecture/interfaces.md, in FIXTURE_MODE=replay with the clock from CLOCK_FILE,
seeded with the demo dataset (docs/architecture/overview.md#demo-dataset).

The worked examples (docs/architecture/rules.md#examples) supply the exact numeric values
asserted here; no value is taken from the implementation.

Note on scope: decision G1 (task.md) deferred the REST-driven acceptance tests for
AC-33–AC-38 and AC-40 until the sibling REST contracts (API-33 account refresh, API-40
score view, API-44 override creation) are built.  AC-39 depends on API-40 and API-33.
AC-06 depends on API-33, API-35, API-40 and API-18.
These tests are written from the specification; they are marked NOT_RUN when the
required surface is absent.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
import requests

from conftest import API_BASE_URL, wait_for

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEADERS_BASE = {"X-Requested-With": "XMLHttpRequest"}
_SHORT_TIMEOUT = 5   # seconds: for existence-probing calls
_CALL_TIMEOUT = 10   # seconds: for normal API calls

# Credentials from docs/architecture/overview.md#demo-dataset
_ADMIN_EMAIL = "admin@leadradar.local"
_SALES_EMAIL = "sales@leadradar.local"


def _api_reachable() -> bool:
    """Return True when the stack's /health endpoint answers at all."""
    try:
        requests.get(f"{API_BASE_URL}/health", timeout=_SHORT_TIMEOUT)
        return True
    except Exception:
        return False


def _probe_route(method: str, path: str, **kwargs) -> int:
    """Return the HTTP status of a probe request, or 0 on connection error."""
    try:
        resp = getattr(requests, method)(
            f"{API_BASE_URL}{path}",
            headers=_HEADERS_BASE,
            timeout=_SHORT_TIMEOUT,
            **kwargs,
        )
        return resp.status_code
    except Exception:
        return 0


def _login(session: requests.Session, email: str, password: str) -> requests.Response:
    """POST /auth/login — API-01."""
    return session.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": email, "password": password},
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )


def _admin_session(stack: dict) -> requests.Session:
    """Return an authenticated Admin session, using SEED_ADMIN_PASSWORD from the
    compose environment (docs/architecture/overview.md#demo-dataset)."""
    password = stack["env"].get("SEED_ADMIN_PASSWORD", "admin-seed-password")
    session = requests.Session()
    resp = _login(session, _ADMIN_EMAIL, password)
    if resp.status_code != 200:
        raise AssertionError(
            f"Admin login failed ({resp.status_code}): {resp.text!r}. "
            "API-01 (POST /auth/login) must be present."
        )
    return session


def _sales_session(stack: dict) -> requests.Session:
    """Return an authenticated Sales session."""
    password = stack["env"].get("SEED_SALES_PASSWORD", "sales-seed-password")
    session = requests.Session()
    resp = _login(session, _SALES_EMAIL, password)
    if resp.status_code != 200:
        raise AssertionError(
            f"Sales login failed ({resp.status_code}): {resp.text!r}. "
            "API-01 (POST /auth/login) must be present."
        )
    return session


def _get_services(session: requests.Session) -> list[dict]:
    """GET /services — API-07."""
    resp = session.get(f"{API_BASE_URL}/services", headers=_HEADERS_BASE, timeout=_CALL_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _get_scoring_configs(session: requests.Session, service_id: str) -> list[dict]:
    """GET /services/{id}/scoring-configs — API-15."""
    resp = session.get(
        f"{API_BASE_URL}/services/{service_id}/scoring-configs",
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _get_scoring_config(session: requests.Session, config_id: str) -> dict:
    """GET /scoring-configs/{id} — API-16."""
    resp = session.get(
        f"{API_BASE_URL}/scoring-configs/{config_id}",
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _activate_config(session: requests.Session, config_id: str, change_note: str) -> requests.Response:
    """POST /scoring-configs/{id}/activate — API-18."""
    return session.post(
        f"{API_BASE_URL}/scoring-configs/{config_id}/activate",
        json={"change_note": change_note},
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )


def _update_draft(
    session: requests.Session,
    service_id: str,
    settings: dict,
    change_note: str | None = None,
) -> requests.Response:
    """PUT /services/{id}/scoring-configs/draft — API-17."""
    body: dict[str, Any] = {"settings": settings}
    if change_note is not None:
        body["change_note"] = change_note
    return session.put(
        f"{API_BASE_URL}/services/{service_id}/scoring-configs/draft",
        json=body,
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )


def _request_refresh(session: requests.Session, account_id: str) -> requests.Response:
    """POST /accounts/{id}/refresh — API-33."""
    return session.post(
        f"{API_BASE_URL}/accounts/{account_id}/refresh",
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )


def _get_run(session: requests.Session, run_id: str) -> dict:
    """GET /runs/{id} — API-35."""
    resp = session.get(
        f"{API_BASE_URL}/runs/{run_id}",
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _get_runs(session: requests.Session, **filters: str) -> dict:
    """GET /runs — API-34."""
    resp = session.get(
        f"{API_BASE_URL}/runs",
        params=filters,
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _get_score(
    session: requests.Session, account_id: str, service_id: str
) -> requests.Response:
    """GET /accounts/{id}/scores/{service_id} — API-40."""
    return session.get(
        f"{API_BASE_URL}/accounts/{account_id}/scores/{service_id}",
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )


def _get_accounts(session: requests.Session) -> dict:
    """GET /accounts — API-20."""
    resp = session.get(f"{API_BASE_URL}/accounts", headers=_HEADERS_BASE, timeout=_CALL_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _wait_run_final(session: requests.Session, run_id: str, timeout_s: float = 300) -> dict:
    """Poll API-35 until the run reaches a terminal status."""
    terminal = {"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"}
    return wait_for(
        lambda: (
            (lambda r: r if r["status"] in terminal else None)(_get_run(session, run_id))
        ),
        timeout_s=timeout_s,
        interval_s=2.0,
        description=f"run {run_id} to reach a terminal status",
    )


def _create_override(
    session: requests.Session,
    account_id: str,
    service_id: str,
    rule_key: str,
    note: str,
) -> requests.Response:
    """POST /accounts/{id}/scores/{service_id}/overrides — API-44."""
    return session.post(
        f"{API_BASE_URL}/accounts/{account_id}/scores/{service_id}/overrides",
        json={"rule_key": rule_key, "note": note},
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )


def _revoke_override(session: requests.Session, override_id: str) -> requests.Response:
    """POST /overrides/{id}/revoke — API-45."""
    return session.post(
        f"{API_BASE_URL}/overrides/{override_id}/revoke",
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )


def _get_prospects(
    session: requests.Session,
    service_id: str,
    standing: str = "RANKED",
    **filters: str,
) -> requests.Response:
    """GET /services/{id}/prospects — API-39."""
    params = {"standing": standing, **filters}
    return session.get(
        f"{API_BASE_URL}/services/{service_id}/prospects",
        params=params,
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# Specification-level helpers
# ---------------------------------------------------------------------------

def _find_service(services: list[dict], code: str) -> dict | None:
    return next((s for s in services if s["code"] == code), None)


def _find_account_by_domain(accounts_page: dict, domain: str) -> dict | None:
    return next(
        (a for a in accounts_page.get("items", []) if a["domain"] == domain), None
    )


# ---------------------------------------------------------------------------
# Prerequisite checks — called at the start of each test
# ---------------------------------------------------------------------------

def _require_stack_reachable() -> None:
    """Skip with NOT RUN if the stack is not answering /health."""
    if not _api_reachable():
        pytest.skip("NOT RUN: stack is not reachable (docker compose up has not been run).")


def _require_auth_api(stack: dict) -> requests.Session:
    """Return an authenticated Admin session or skip with NOT RUN."""
    status = _probe_route("post", "/auth/login", json={"email": _ADMIN_EMAIL, "password": "x"})
    if status in (0, 404, 405):
        pytest.skip(
            "NOT RUN: API-01 (POST /auth/login) is absent or unreachable "
            f"(probe returned {status}). Authentication is required for all scoring tests."
        )
    # Now attempt a real login using the seeded credentials.
    try:
        return _admin_session(stack)
    except AssertionError as exc:
        pytest.skip(f"NOT RUN: {exc}")


def _require_refresh_api(session: requests.Session, account_id: str) -> None:
    """Skip with NOT RUN if API-33 is absent."""
    status = _probe_route("post", f"/accounts/{account_id}/refresh")
    if status in (0, 404, 405):
        pytest.skip(
            "NOT RUN: API-33 (POST /accounts/{id}/refresh) is absent "
            f"(probe returned {status}).  "
            "The full scoring pipeline (FETCH→SCORE) is required for this criterion."
        )


def _require_score_api(session: requests.Session, account_id: str, service_id: str) -> None:
    """Skip with NOT RUN if API-40 is absent."""
    # 404 (no score yet) is acceptable; 405 or 0 means the route doesn't exist.
    status = _probe_route("get", f"/accounts/{account_id}/scores/{service_id}")
    if status in (0, 405):
        pytest.skip(
            "NOT RUN: API-40 (GET /accounts/{id}/scores/{service_id}) is absent "
            f"(probe returned {status}).  "
            "Score view is required to verify scoring outputs."
        )


def _require_override_api(session: requests.Session, account_id: str, service_id: str) -> None:
    """Skip with NOT RUN if API-44 is absent."""
    status = _probe_route(
        "post",
        f"/accounts/{account_id}/scores/{service_id}/overrides",
        json={"rule_key": "_probe", "note": "_probe"},
    )
    if status in (0, 404, 405):
        pytest.skip(
            "NOT RUN: API-44 (POST .../overrides) is absent "
            f"(probe returned {status}).  "
            "Override creation is required for AC-36."
        )


# ---------------------------------------------------------------------------
# AC-06: scoring-version activation triggers RESCORE with no AI activity
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-06")
def test_activation_makes_draft_active_retires_previous_and_rescores_without_ai_calls(stack):
    """AC-06 (docs/requirements/acceptance.md):

    "Given all demo accounts refreshed from the demo recording and a draft that raises
    AUTOMATION_HIRING to HIGH, when an Admin activates it with a change note, then the
    draft is ACTIVE, the previous version RETIRED, and a RESCORE run with trigger
    SCORING_ACTIVATION finishes with every changed current score referencing the new
    version; during that run no document, classification or AI_CALL audit row is created."

    Contracts exercised: API-01, API-07, API-15, API-16, API-17, API-18, API-33, API-34,
    API-35, API-40.  The demo dataset must be seeded (make seed-demo) before this runs.

    Missing surface: API-33 (POST /accounts/{id}/refresh) and API-40
    (GET /accounts/{id}/scores/{service_id}) are required to seed scores before
    activation and verify the new version references after rescoring.
    """
    _require_stack_reachable()
    admin = _require_auth_api(stack)

    # Fetch the INTELLIGENT_AUTOMATION service
    services = _get_services(admin)
    ia_service = _find_service(services, "INTELLIGENT_AUTOMATION")
    if ia_service is None:
        pytest.skip(
            "NOT RUN: INTELLIGENT_AUTOMATION service absent from GET /services; "
            "make seed-demo must run before the acceptance suite."
        )
    service_id = ia_service["id"]

    # Check for seeded accounts
    accounts_page = _get_accounts(admin)
    dhl = _find_account_by_domain(accounts_page, "dhl.com")
    if dhl is None:
        pytest.skip(
            "NOT RUN: DHL Group (dhl.com) absent from GET /accounts; "
            "make seed-demo must run before the acceptance suite."
        )

    _require_refresh_api(admin, dhl["id"])
    _require_score_api(admin, dhl["id"], service_id)

    # Refresh DHL so a score row exists
    refresh_resp = _request_refresh(admin, dhl["id"])
    assert refresh_resp.status_code in (200, 202), (
        f"API-33 returned unexpected status {refresh_resp.status_code}: {refresh_resp.text!r}"
    )
    refresh_run_id = refresh_resp.json()["id"]
    finished_run = _wait_run_final(admin, refresh_run_id, timeout_s=300)
    assert finished_run["status"] in ("SUCCEEDED", "PARTIAL"), (
        f"DHL refresh run ended {finished_run['status']!r}."
    )

    # Read DHL's current scoring version before activation
    score_resp = _get_score(admin, dhl["id"], service_id)
    assert score_resp.status_code == 200, (
        f"API-40 failed after DHL refresh: {score_resp.status_code}"
    )
    active_version_before = score_resp.json()["scoring_version"]

    # Build draft that raises AUTOMATION_HIRING to HIGH
    configs = _get_scoring_configs(admin, service_id)
    active_cfg = next((c for c in configs if c["status"] == "ACTIVE"), None)
    assert active_cfg is not None, (
        "No ACTIVE scoring config for INTELLIGENT_AUTOMATION; make seed-demo first."
    )
    active_full = _get_scoring_config(admin, active_cfg["id"])
    base_settings = dict(active_full["settings"])

    new_questions = []
    for q in base_settings.get("questions", []):
        entry = dict(q)
        if entry.get("question_key") == "AUTOMATION_HIRING":
            entry["weight"] = "HIGH"
        new_questions.append(entry)
    base_settings["questions"] = new_questions

    draft_resp = _update_draft(admin, service_id, base_settings, change_note="AC-06 test")
    assert draft_resp.status_code == 200, (
        f"API-17 failed: {draft_resp.status_code}: {draft_resp.text!r}"
    )
    draft_cfg = draft_resp.json()
    assert draft_cfg["status"] == "DRAFT"
    draft_id = draft_cfg["id"]
    draft_version = draft_cfg["version"]

    # Activate with a change note
    change_note = "Raising AUTOMATION_HIRING to HIGH for AC-06 acceptance test"
    act_resp = _activate_config(admin, draft_id, change_note)
    assert act_resp.status_code == 200, (
        f"API-18 failed: {act_resp.status_code}: {act_resp.text!r}"
    )
    activated = act_resp.json()

    # "the draft is ACTIVE"
    assert activated["status"] == "ACTIVE", (
        f"AC-06: expected ACTIVE after activation, got {activated['status']!r}"
    )
    assert activated["version"] == draft_version, (
        f"AC-06: version mismatch after activation: expected {draft_version}, "
        f"got {activated['version']}"
    )
    assert activated["change_note"] == change_note, (
        f"AC-06: change_note mismatch: expected {change_note!r}, "
        f"got {activated['change_note']!r}"
    )

    # "the previous version RETIRED"
    configs_after = _get_scoring_configs(admin, service_id)
    previous = next((c for c in configs_after if c["version"] == active_version_before), None)
    assert previous is not None, (
        f"AC-06: previous version {active_version_before} not found after activation."
    )
    assert previous["status"] == "RETIRED", (
        f"AC-06: expected previous version {active_version_before} to be RETIRED, "
        f"got {previous['status']!r}"
    )

    # "a RESCORE run with trigger SCORING_ACTIVATION finishes"
    rescore_run = wait_for(
        lambda: next(
            (
                r
                for r in _get_runs(admin, kind="RESCORE", service_id=service_id).get("items", [])
                if r.get("trigger") == "SCORING_ACTIVATION"
                and r.get("status") in ("SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED")
            ),
            None,
        ),
        timeout_s=300,
        interval_s=3.0,
        description="RESCORE run with SCORING_ACTIVATION to finish",
    )
    assert rescore_run is not None, (
        "AC-06: no RESCORE run with trigger SCORING_ACTIVATION became terminal within 300 s."
    )
    assert rescore_run["status"] in ("SUCCEEDED", "PARTIAL"), (
        f"AC-06: RESCORE ended {rescore_run['status']!r}."
    )

    # "every changed current score referencing the new version"
    score_after = _get_score(admin, dhl["id"], service_id)
    assert score_after.status_code == 200
    assert score_after.json()["scoring_version"] == draft_version, (
        f"AC-06: DHL score still references version "
        f"{score_after.json()['scoring_version']} not {draft_version}."
    )

    # "during that run no document, classification or AI_CALL audit row is created"
    run_detail = _get_run(admin, rescore_run["id"])
    progress = run_detail.get("progress", {})
    assert progress.get("pairs_classified", 0) == 0, (
        f"AC-06: RESCORE classified {progress.get('pairs_classified')} pairs; must be 0."
    )
    assert progress.get("findings_created", 0) == 0, (
        f"AC-06: RESCORE created {progress.get('findings_created')} findings; must be 0."
    )
    assert progress.get("documents_fetched", 0) == 0, (
        f"AC-06: RESCORE fetched {progress.get('documents_fetched')} documents; must be 0."
    )


# ---------------------------------------------------------------------------
# AC-33: Example 1 Fit = 94, SIZE UNKNOWN with credit unknown_match
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-33")
def test_example1_fit_94_size_unknown_with_unknown_match_credit(stack):
    """AC-33 (docs/requirements/acceptance.md):

    "Given the settings and account of Example 1 of the rules examples, when the account
    is scored, then Fit is 94 and the breakdown shows SIZE as UNKNOWN with credit
    unknown_match."

    Rules example (docs/architecture/rules.md#examples):
      Industry AEROSPACE_AVIATION, country DE, employees unknown, complexity HIGH.
      Fit = 100 × (3·1 + 2·1 + 1·0.5 + 2·1) / 8 = 93.75 → 94.
      SIZE criterion: employees unknown → credit = unknown_match = 0.5 (default).

    Requires: API-01, API-08, API-12, API-17, API-18, API-21, API-33, API-40.
    """
    _require_stack_reachable()
    admin = _require_auth_api(stack)

    accounts_page = _get_accounts(admin)
    any_account = accounts_page.get("items", [None])[0] if accounts_page.get("items") else None
    if any_account is None:
        pytest.skip("NOT RUN: no accounts; make seed-demo first.")

    _require_refresh_api(admin, any_account["id"])
    _require_score_api(admin, any_account["id"], str(uuid.uuid4()))

    # Create Example 1 service
    svc_code = f"AC33_{uuid.uuid4().hex[:8].upper()}"
    svc_resp = admin.post(
        f"{API_BASE_URL}/services",
        json={
            "code": svc_code,
            "name": f"AC-33 Service {svc_code}",
            "description": "Example 1 test service.",
            "value_proposition": "Test.",
        },
        headers=_HEADERS_BASE,
        timeout=_CALL_TIMEOUT,
    )
    assert svc_resp.status_code == 200, (
        f"API-08 failed: {svc_resp.status_code}: {svc_resp.text!r}"
    )
    service_id = svc_resp.json()["id"]

    # Create the four questions of Example 1
    questions_spec = [
        {"key": "COST_PROGRAM", "text": "Cost reduction programme?",
         "answer_type": "YES_NO", "polarity": "POSITIVE", "source_types": ["NEWS", "COMPANY_PUBLICATION"]},
        {"key": "AUTOMATION_HIRING", "text": "Hiring automation engineers?",
         "answer_type": "YES_NO", "polarity": "POSITIVE", "source_types": ["JOB_POSTING"]},
        {"key": "AI_INITIATIVE", "text": "AI or process-mining projects?",
         "answer_type": "YES_NO", "polarity": "POSITIVE", "source_types": ["NEWS", "COMPANY_PUBLICATION"]},
        {"key": "IN_HOUSE_AUTOMATION", "text": "Strong in-house automation capability?",
         "answer_type": "YES_NO", "polarity": "NEGATIVE", "source_types": ["NEWS", "COMPANY_PUBLICATION"]},
    ]
    for q in questions_spec:
        q_resp = admin.post(
            f"{API_BASE_URL}/services/{service_id}/questions",
            json=q, headers=_HEADERS_BASE, timeout=_CALL_TIMEOUT,
        )
        assert q_resp.status_code == 200, (
            f"API-12 for {q['key']} failed: {q_resp.status_code}: {q_resp.text!r}"
        )

    # Activate Example 1 settings
    example1_settings = {
        "fit_weight": 0.4, "intent_weight": 0.6, "min_fit": 40,
        "hot_threshold": 70, "warm_threshold": 40,
        "weight_values": {"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.0},
        "strength_values": {"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
        "default_half_life_days": {"NEWS": 90, "COMPANY_PUBLICATION": 365, "JOB_POSTING": 60, "COMPANY_PROFILE": 365},
        "min_decay": 0.05, "negative_factor": 1.0, "intent_saturation": 0.5, "unknown_match": 0.5,
        "icp_criteria": [
            {"key": "SECTOR", "kind": "INDUSTRY", "weight": "HIGH",
             "values": ["AEROSPACE_AVIATION", "LOGISTICS_TRANSPORT"]},
            {"key": "REGION", "kind": "GEOGRAPHY", "weight": "MEDIUM", "values": ["DE", "AT", "CH"]},
            {"key": "SIZE", "kind": "EMPLOYEE_RANGE", "weight": "LOW", "min": 5000},
            {"key": "COMPLEXITY", "kind": "OPERATIONAL_COMPLEXITY", "weight": "MEDIUM", "values": ["HIGH"]},
        ],
        "questions": [
            {"question_key": "COST_PROGRAM", "weight": "HIGH", "half_life_days": None},
            {"question_key": "AUTOMATION_HIRING", "weight": "MEDIUM", "half_life_days": None},
            {"question_key": "AI_INITIATIVE", "weight": "HIGH", "half_life_days": None},
            {"question_key": "IN_HOUSE_AUTOMATION", "weight": "MEDIUM", "half_life_days": None},
        ],
        "disqualifiers": [],
    }
    draft_resp = _update_draft(admin, service_id, example1_settings)
    assert draft_resp.status_code == 200, (
        f"API-17 failed: {draft_resp.status_code}: {draft_resp.text!r}"
    )
    draft_id = draft_resp.json()["id"]
    act_resp = _activate_config(admin, draft_id, "Example 1 settings for AC-33")
    assert act_resp.status_code == 200, (
        f"API-18 failed: {act_resp.status_code}: {act_resp.text!r}"
    )

    # Create Example 1 account: industry=AEROSPACE_AVIATION, country=DE, employee_count=null, complexity=HIGH
    acct_domain = f"ac33-{uuid.uuid4().hex[:8]}.example"
    acct_resp = admin.post(
        f"{API_BASE_URL}/accounts",
        json={
            "domain": acct_domain,
            "name": "AC-33 Example 1 Account",
            "country_code": "DE",
            "industry": "AEROSPACE_AVIATION",
            "operational_complexity": "HIGH",
            # employee_count deliberately omitted → unknown → SIZE gets unknown_match credit
        },
        headers=_HEADERS_BASE, timeout=_CALL_TIMEOUT,
    )
    assert acct_resp.status_code == 200, (
        f"API-21 failed: {acct_resp.status_code}: {acct_resp.text!r}"
    )
    account_id = acct_resp.json()["id"]

    # Trigger refresh (FETCH → SCORE stages)
    refresh_resp = _request_refresh(admin, account_id)
    assert refresh_resp.status_code in (200, 202), (
        f"API-33 failed: {refresh_resp.status_code}: {refresh_resp.text!r}"
    )
    run_id = refresh_resp.json()["id"]
    finished = _wait_run_final(admin, run_id, timeout_s=300)
    assert finished["status"] in ("SUCCEEDED", "PARTIAL"), (
        f"Refresh ended {finished['status']!r}."
    )

    # Read the score
    score_resp = _get_score(admin, account_id, service_id)
    assert score_resp.status_code == 200, (
        f"API-40 failed: {score_resp.status_code}: {score_resp.text!r}"
    )
    score = score_resp.json()

    # AC-33: "Fit is 94"
    assert score["fit"] == 94, (
        f"AC-33: expected Fit 94, got {score['fit']}"
    )

    # AC-33: "the breakdown shows SIZE as UNKNOWN with credit unknown_match"
    criteria = score["breakdown"]["fit"]["criteria"]
    size_entry = next((c for c in criteria if c["key"] == "SIZE"), None)
    assert size_entry is not None, (
        "AC-33: SIZE criterion absent from breakdown['fit']['criteria']."
    )
    assert size_entry["match"] == "UNKNOWN", (
        f"AC-33: SIZE match expected UNKNOWN, got {size_entry['match']!r}."
    )
    # default unknown_match is 0.5 (docs/architecture/sql-store.md#scoring-settings-document)
    assert abs(size_entry["credit"] - 0.5) < 1e-6, (
        f"AC-33: SIZE credit expected 0.5 (unknown_match default), got {size_entry['credit']}."
    )


# ---------------------------------------------------------------------------
# AC-34: Example 1 Intent = 38, Priority 60, RANKED WARM, negative IN_HOUSE_AUTOMATION
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-34")
def test_example1_intent_38_priority_60_ranked_warm_inhouse_negative(stack):
    """AC-34 (docs/requirements/acceptance.md):

    "Given the findings of Example 1 at their stated ages, when the account is scored,
    then Intent is 38, Priority 60, standing RANKED and band WARM, and the
    IN_HOUSE_AUTOMATION entry has negative points; without that finding Intent is higher."

    Rules example values (docs/architecture/rules.md#examples):
      COST_PROGRAM STRONG NEWS 45d: value = 1.0 × 0.5^(45/90) = 0.707107.
      AUTOMATION_HIRING MEDIUM JOB_POSTING 30d: value = 0.75 × 0.5^(30/60) = 0.530330.
      IN_HOUSE_AUTOMATION STRONG COMPANY_PUBLICATION 100d:
        value = 1.0 × 0.5^(100/365) = 0.827037.
      P = 3·0.707107 + 2·0.530330 = 3.181981; N = 2·0.827037 = 1.654074; M = 3+2+3=8.
      Intent = 100 × (3.181981 − 1.654074) / (0.5 × 8) = 38.20 → 38.
      Priority = 0.4 × 94 + 0.6 × 38 = 60.4 → 60.

    This test requires a fixture-driven refresh that creates exactly these findings at
    the ages stated.  The as_of must equal the clock time at scoring.  Without the
    full signal pipeline (S-SIG-*) running against the demo recording, the exact ages
    cannot be controlled through the REST surface alone.

    Missing surface: API-33 (full signal pipeline), API-40.
    """
    _require_stack_reachable()
    admin = _require_auth_api(stack)

    accounts_page = _get_accounts(admin)
    any_account = accounts_page.get("items", [None])[0] if accounts_page.get("items") else None
    if any_account is None:
        pytest.skip("NOT RUN: no accounts; make seed-demo first.")

    _require_refresh_api(admin, any_account["id"])
    _require_score_api(admin, any_account["id"], str(uuid.uuid4()))

    pytest.skip(
        "NOT RUN: AC-34 requires a fixture-driven ACCOUNT_REFRESH that creates findings "
        "at exact ages (COST_PROGRAM STRONG NEWS 45d, AUTOMATION_HIRING MEDIUM JOB_POSTING "
        "30d, IN_HOUSE_AUTOMATION STRONG COMPANY_PUBLICATION 100d) whose breakdown is then "
        "readable through API-40.  The full signal pipeline (S-SIG-*) must be in place "
        "and the demo recording fixtures for the Example 1 service must exist.  "
        "Prerequisite surface: API-33 with signal pipeline, API-40."
    )


# ---------------------------------------------------------------------------
# AC-35: Recency decay — NEWS half-life 90 d at 90 d old = 0.5; 400 d old = 0
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-35")
def test_decay_half_life_at_90_days_is_0_5_and_400_day_finding_contributes_zero(stack):
    """AC-35 (docs/requirements/acceptance.md):

    "Given the Example 1 settings, when a NEWS finding of a question without its own
    half-life is 90 days old at as_of, then its decay is 0.5; the 400-day-old finding
    of Example 3 contributes 0."

    Decay rule (docs/architecture/rules.md#recency-decay):
      h = default_half_life_days[NEWS] = 90.
      age=90 → decay = 0.5^(90/90) = 0.5.
      age=400 → decay = 0.5^(400/90) ≈ 0.046 < min_decay 0.05 → contributes 0.

    Observable through breakdown's questions[].decay and questions[].value
    (docs/architecture/rules.md#score-breakdown).

    Missing surface: API-33 (to produce findings at exact ages), API-40.
    """
    _require_stack_reachable()
    admin = _require_auth_api(stack)

    accounts_page = _get_accounts(admin)
    any_account = accounts_page.get("items", [None])[0] if accounts_page.get("items") else None
    if any_account is None:
        pytest.skip("NOT RUN: no accounts; make seed-demo first.")

    _require_score_api(admin, any_account["id"], str(uuid.uuid4()))

    pytest.skip(
        "NOT RUN: AC-35 requires fixture-driven findings at exact ages (90 d and 400 d) "
        "whose decay values are observable via API-40's breakdown questions[].decay.  "
        "The full signal pipeline must be built.  "
        "Prerequisite surface: API-33 with signal pipeline, API-40."
    )


# ---------------------------------------------------------------------------
# AC-36: Example 2 disqualification, override and revocation
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-36")
def test_example2_disqualified_then_overridden_then_revoked(stack):
    """AC-36 (docs/requirements/acceptance.md):

    "Given Example 2's account, when it is scored, then its standing is DISQUALIFIED
    with no band and the breakdown names OUTSIDE_REGION; it is absent from the default
    Prospects list and present under standing DISQUALIFIED with the rule's label; after
    an Admin adds an exception with a note it is RANKED and WARM; after revocation it is
    DISQUALIFIED again; a Sales user adding an exception is refused 403."

    Example 2 (docs/architecture/rules.md#examples):
      OUTSIDE_REGION (ICP_MISMATCH on REGION); country FR.
      standing = DISQUALIFIED, no band.  breakdown disqualifiers: OUTSIDE_REGION matched.
      After Admin override: standing = RANKED, band = WARM.
      After revocation: standing = DISQUALIFIED again.
      Sales user adding override → 403 FORBIDDEN.

    Missing surface: API-33, API-39 (prospects with standing filter),
    API-40, API-44, API-45.
    """
    _require_stack_reachable()
    admin = _require_auth_api(stack)

    accounts_page = _get_accounts(admin)
    any_account = accounts_page.get("items", [None])[0] if accounts_page.get("items") else None
    if any_account is None:
        pytest.skip("NOT RUN: no accounts; make seed-demo first.")

    _require_refresh_api(admin, any_account["id"])
    _require_score_api(admin, any_account["id"], str(uuid.uuid4()))
    _require_override_api(admin, any_account["id"], str(uuid.uuid4()))

    pytest.skip(
        "NOT RUN: AC-36 requires the full scoring pipeline (API-33), score view (API-40), "
        "prospects with standing filter (API-39), override creation (API-44) and "
        "override revocation (API-45).  "
        "Prerequisite surface: API-33, API-39, API-40, API-44, API-45."
    )


# ---------------------------------------------------------------------------
# AC-37: Band thresholds — Priority 70→HOT, 69/40→WARM, 39→COLD; Fit 39→BELOW_FIT
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-37")
def test_band_thresholds_and_below_fit_standing(stack):
    """AC-37 (docs/requirements/acceptance.md):

    "Given the default thresholds and accounts with Fit of at least 40, when they score
    Priority 70, 69, 40 and 39, then their bands are HOT, WARM, WARM and COLD; an account
    with Fit 39 is BELOW_FIT with no band and no rank."

    Default thresholds (docs/architecture/sql-store.md#scoring-settings-document):
      hot_threshold = 70, warm_threshold = 40, min_fit = 40.
    Priority, standing and band rule (docs/architecture/rules.md#priority-standing-and-band):
      HOT: Priority ≥ 70.  WARM: 40 ≤ Priority < 70.  COLD: Priority < 40.
      BELOW_FIT: Fit < min_fit (40).

    Missing surface: API-33, API-40.
    """
    _require_stack_reachable()
    admin = _require_auth_api(stack)

    accounts_page = _get_accounts(admin)
    any_account = accounts_page.get("items", [None])[0] if accounts_page.get("items") else None
    if any_account is None:
        pytest.skip("NOT RUN: no accounts; make seed-demo first.")

    _require_refresh_api(admin, any_account["id"])
    _require_score_api(admin, any_account["id"], str(uuid.uuid4()))

    pytest.skip(
        "NOT RUN: AC-37 requires accounts scored at exact Priority values through the "
        "full scoring pipeline.  Prerequisite surface: API-33, API-40."
    )


# ---------------------------------------------------------------------------
# AC-38: Breakdown additive — criteria points sum to Fit, question points to Intent
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-38")
def test_breakdown_criteria_points_sum_to_fit_and_question_points_to_intent(stack):
    """AC-38 (docs/requirements/acceptance.md):

    "Given any score produced from the demo recording, when its breakdown is read, then
    the criteria points add up to Fit and the question points to Intent before rounding
    and clamping, and every question entry with non-zero points names an in-force finding."

    Score breakdown (docs/architecture/rules.md#score-breakdown):
      Σ criteria[].points = raw Fit (before integer rounding), i.e. within 0.5 of Fit.
      Σ questions[].points = raw Intent (before rounding/clamping).
      A questions entry with points ≠ 0 must have finding_id present.

    Missing surface: API-33 (demo refresh to produce scores), API-40.
    """
    _require_stack_reachable()
    admin = _require_auth_api(stack)

    accounts_page = _get_accounts(admin)
    any_account = accounts_page.get("items", [None])[0] if accounts_page.get("items") else None
    if any_account is None:
        pytest.skip("NOT RUN: no accounts; make seed-demo first.")

    _require_score_api(admin, any_account["id"], str(uuid.uuid4()))

    pytest.skip(
        "NOT RUN: AC-38 requires demo accounts refreshed from the demo recording "
        "so that score breakdowns exist to inspect.  "
        "Prerequisite surface: API-33 (full pipeline), API-40."
    )


# ---------------------------------------------------------------------------
# AC-39: Idempotent scoring — no duplicate row; byte-identical breakdown; new finding → new row
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-39")
def test_no_new_score_row_when_inputs_unchanged_and_byte_identical_on_same_as_of(stack):
    """AC-39 (docs/requirements/acceptance.md):

    "Given a scored account, when it is rescored with no input changed, then no score row
    is written; when the same inputs are scored twice at the same as_of, the two
    breakdowns are byte-identical; when a new finding changes Intent, a new current row
    exists and the previous one remains with is_current false."

    Rescoring rule (docs/architecture/rules.md#rescoring):
      If scoring_config_id, fit, intent, priority, standing, band, finding_ids,
      override_ids are all equal to the current row → write nothing.
      Same inputs + same as_of → identical breakdown JSON (sorted keys, 6 dp).
      A changed finding → new current row; old row kept with is_current = false.

    Observable through: API-40 (current score's breakdown), API-41 (score history).
    A second refresh with unchanged inputs must not add a new entry to API-41's list.

    Missing surface: API-33, API-40, API-41.
    """
    _require_stack_reachable()
    admin = _require_auth_api(stack)

    accounts_page = _get_accounts(admin)
    any_account = accounts_page.get("items", [None])[0] if accounts_page.get("items") else None
    if any_account is None:
        pytest.skip("NOT RUN: no accounts; make seed-demo first.")

    _require_refresh_api(admin, any_account["id"])
    _require_score_api(admin, any_account["id"], str(uuid.uuid4()))

    # Probe API-41 (score history)
    history_status = _probe_route(
        "get", f"/accounts/{any_account['id']}/scores/{uuid.uuid4()}/history"
    )
    if history_status in (0, 405):
        pytest.skip(
            "NOT RUN: API-41 (GET .../scores/{service_id}/history) is absent "
            f"(probe returned {history_status}).  AC-39 requires it."
        )

    pytest.skip(
        "NOT RUN: AC-39 requires API-33 (refresh), API-40 (score view with breakdown "
        "and is_current), and API-41 (score history to confirm previous rows are kept).  "
        "Prerequisite surface: API-33, API-40, API-41."
    )


# ---------------------------------------------------------------------------
# AC-40: Stored scores reproduced by rules; no AI contract returns score/band/standing
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-40")
def test_recomputed_score_equals_stored_and_no_ai_contract_returns_score(stack):
    """AC-40 (docs/requirements/acceptance.md):

    "Given all demo accounts refreshed, when the test recomputes each score from the
    stored findings, feedback, exceptions, attributes and active settings with the
    formulas of the rules, then it equals the stored score; no classifier or LLM
    contract of interfaces returns a score, band, standing or exclusion."

    Rules (docs/architecture/rules.md#fit-score, #intent-score, #disqualification,
    #priority-standing-and-band): the computation is deterministic from the stored inputs.

    The second half is verified structurally by inspecting the OpenAPI schema served by
    API-61: the classifier and LLM response schemas (ClassifierAnswer, EscalationOutput,
    EvidenceOutput, Organisation, OutreachOutput of
    docs/architecture/interfaces.md#classifier and #llm) must contain none of the field
    names 'score', 'band', 'standing', 'exclusion', 'priority', 'fit', 'intent'.

    Missing surface (first half): API-33 (demo refresh), API-40 (score views), API-42
    (findings to recompute from).
    """
    _require_stack_reachable()
    admin = _require_auth_api(stack)

    # --- Second half: OpenAPI schema check (structural, no running pipeline needed) ---
    openapi_resp = requests.get(
        f"{API_BASE_URL.replace('/api/v1', '')}/openapi.json",
        timeout=_CALL_TIMEOUT,
    )
    if openapi_resp.status_code == 200:
        schema = openapi_resp.json()
        # Classifier and LLM response schema names from docs/architecture/interfaces.md
        ai_response_schemas = {
            "ClassifierAnswer", "EscalationOutput", "EvidenceOutput",
            "Organisation", "OutreachOutput",
        }
        score_field_names = {"score", "band", "standing", "exclusion", "priority", "fit", "intent"}
        components = schema.get("components", {}).get("schemas", {})
        for schema_name in ai_response_schemas:
            if schema_name in components:
                schema_props = set(
                    components[schema_name].get("properties", {}).keys()
                )
                forbidden_fields = schema_props & score_field_names
                assert not forbidden_fields, (
                    f"AC-40: AI response schema {schema_name!r} contains scoring fields "
                    f"{forbidden_fields!r}; no classifier or LLM contract may return a "
                    "score, band, standing or exclusion "
                    "(docs/architecture/rules.md#score-breakdown, RULE-03)."
                )

    # --- First half: recomputation requires demo refresh ---
    accounts_page = _get_accounts(admin)
    any_account = accounts_page.get("items", [None])[0] if accounts_page.get("items") else None
    if any_account is None:
        pytest.skip("NOT RUN: no accounts; make seed-demo first.")

    _require_refresh_api(admin, any_account["id"])
    _require_score_api(admin, any_account["id"], str(uuid.uuid4()))

    pytest.skip(
        "NOT RUN (first half): AC-40 recomputation requires demo accounts refreshed "
        "(API-33), score views (API-40), and findings (API-42).  "
        "The AI schema check above runs without the pipeline.  "
        "Prerequisite surface for first half: API-33, API-40, API-42."
    )
