"""Acceptance tests for the signal pipeline: document triage, classification routing,
escalation/evidence, findings and reclassification.

Criteria covered: AC-20, AC-21, AC-22, AC-24, AC-25, AC-26.
Source of truth: docs/requirements/acceptance.md (Ingestion and signal detection section).

All six criteria require a full account-refresh pipeline (FL-07) whose surface
(API-33 POST /accounts/{id}/refresh → worker FETCH + NORMALISE + CHUNK + SIGNAL + SCORE
stages) is owned by S-ING-* / S-PIP-* / S-RUN-02 and is not part of this task's rows
(S-SIG-01, S-SIG-02, S-SIG-03, S-SIG-05, S-SIG-06, S-SIG-09).

Per task decision G1 (task.md):
  "Ship the rules and AI ports here … and defer AC-20, AC-21, AC-22, AC-24, AC-25, AC-26
   to a later pipeline-integration task that owns API-33 + fetch + process + signal + score
   in replay mode."

Each test below is written from the acceptance criterion only.  It probes for the
prerequisite REST surface (API-33, API-35, API-42) and skips with NOT RUN when absent,
recording the missing surface.  None of these tests will pass until the pipeline-integration
task delivers the full stack in replay mode.
"""

from __future__ import annotations

import re
import uuid

import pytest
import requests

from conftest import API_BASE_URL, wait_for

_HEADERS_BASE = {"X-Requested-With": "XMLHttpRequest"}

# Demo dataset credentials (docs/architecture/overview.md#demo-dataset)
_ADMIN_EMAIL = "admin@leadradar.local"
_SALES_EMAIL = "sales@leadradar.local"


def _login(session: requests.Session, email: str, password: str) -> requests.Response:
    """POST /auth/login — API-01."""
    return session.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": email, "password": password},
        headers=_HEADERS_BASE,
        timeout=10,
    )


def _admin_session(stack: dict) -> requests.Session:
    password = stack["env"].get("SEED_ADMIN_PASSWORD", "admin-seed-password")
    session = requests.Session()
    resp = _login(session, _ADMIN_EMAIL, password)
    assert resp.status_code == 200, (
        f"Admin login failed ({resp.status_code}): {resp.text!r}. "
        "API-01 (POST /auth/login) must be present for these tests."
    )
    return session


def _get_accounts(session: requests.Session) -> dict:
    """GET /accounts — API-20."""
    resp = session.get(f"{API_BASE_URL}/accounts", headers=_HEADERS_BASE, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _find_account_by_domain(accounts_page: dict, domain: str) -> dict | None:
    return next(
        (a for a in accounts_page.get("items", []) if a["domain"] == domain), None
    )


def _request_refresh(session: requests.Session, account_id: str) -> requests.Response:
    """POST /accounts/{id}/refresh — API-33."""
    return session.post(
        f"{API_BASE_URL}/accounts/{account_id}/refresh",
        headers=_HEADERS_BASE,
        timeout=10,
    )


def _get_run(session: requests.Session, run_id: str) -> dict:
    """GET /runs/{id} — API-35."""
    resp = session.get(
        f"{API_BASE_URL}/runs/{run_id}",
        headers=_HEADERS_BASE,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _get_findings(
    session: requests.Session, account_id: str, service_id: str | None = None
) -> requests.Response:
    """GET /accounts/{id}/findings — API-42."""
    params = {}
    if service_id:
        params["service_id"] = service_id
    return session.get(
        f"{API_BASE_URL}/accounts/{account_id}/findings",
        params=params,
        headers=_HEADERS_BASE,
        timeout=10,
    )


def _wait_run_final(session: requests.Session, run_id: str, timeout_s: float = 600) -> dict:
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


def _probe_api33_api42(stack: dict) -> requests.Session:
    """Return an admin session after probing for API-01, API-33 and API-42.

    Raises pytest.skip when any prerequisite is absent.
    """
    try:
        admin = _admin_session(stack)
    except AssertionError as exc:
        pytest.skip(f"NOT RUN: {exc}")

    accounts_page = _get_accounts(admin)
    dhl = _find_account_by_domain(accounts_page, "dhl.com")
    if dhl is None:
        pytest.skip(
            "NOT RUN: DHL Group (dhl.com) is absent from GET /accounts; "
            "make seed-demo must be run before the acceptance suite."
        )

    refresh_probe = _request_refresh(admin, dhl["id"])
    if refresh_probe.status_code in (404, 405):
        pytest.skip(
            "NOT RUN: API-33 (POST /accounts/{id}/refresh) answered "
            f"{refresh_probe.status_code}; it must be built before this AC can run. "
            "Missing surface: API-33 (account refresh)."
        )

    findings_probe = _get_findings(admin, dhl["id"])
    if findings_probe.status_code in (404, 405):
        pytest.skip(
            "NOT RUN: API-42 (GET /accounts/{id}/findings) answered "
            f"{findings_probe.status_code}; it must be built before this AC can run. "
            "Missing surface: API-42 (findings list)."
        )

    return admin


# ---------------------------------------------------------------------------
# AC-20: Every new non-duplicate document has one triage row; NOT_ABOUT_ACCOUNT;
#         website documents have no about_account_p
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-20")
def test_document_triage_one_row_per_document_and_irrelevant_marked_not_about_account(stack):
    """AC-20 (docs/requirements/acceptance.md):

    "Given the demo recording, when DHL Group is refreshed, then every new non-duplicate
    document has one triage row; the recorded article that mentions DHL only in passing is
    NOT_ABOUT_ACCOUNT and has no classification; documents from DHL's own website have no
    about_account_p."

    Contracts exercised: API-01, API-33, API-35, API-42.
    The triage outcome (about_account_p, NOT_ABOUT_ACCOUNT status) is visible through the
    document's triage row exposed on each FindingView's document field and, indirectly, by
    the absence of classifications for NOT_ABOUT_ACCOUNT documents (AC-20 says "has no
    classification").

    Missing surface: API-33 (POST /accounts/{id}/refresh) and API-42 (GET
    /accounts/{id}/findings) are required.  The document_triage table is internal; its
    observable effect is the absence of findings for NOT_ABOUT_ACCOUNT documents and the
    absence of about_account_p on website documents.  Both are deferred per task decision G1:
    the full signal pipeline (FETCH + TRIAGE stage) is not built in this task.
    """
    _probe_api33_api42(stack)
    pytest.skip(
        "NOT RUN (deferred per task decision G1): AC-20 requires a full account-refresh "
        "run (API-33 → FETCH → TRIAGE stage) whose surface (document_triage rows via the "
        "signal pipeline) is not present in this task.  The triage rules and adapter are "
        "built (S-SIG-01 unit/contract tests pass) but the pipeline-integration task owns "
        "the end-to-end surface.  "
        "Missing surface: API-33 account-refresh pipeline with TRIAGE stage, "
        "document_triage rows observable through API-42."
    )


# ---------------------------------------------------------------------------
# AC-21: Each kept passage has one classification per active question; idempotency
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-21")
def test_each_passage_has_one_classification_per_active_question_and_refresh_is_idempotent(stack):
    """AC-21 (docs/requirements/acceptance.md):

    "Given a kept news document and the Intelligent Automation questions, when it is
    classified, then each selected passage has one classification per active question whose
    source types include NEWS and none for AUTOMATION_HIRING; each classification records
    the classifier CLASSIFIER_PROVIDER names; a second refresh adds no classification for
    the same passage, question and revision."

    Contracts exercised: API-01, API-33, API-35, API-42.
    The classification count per passage is an internal store property (classification table)
    whose observable effect is via findings (API-42) — if a question has no finding and no
    classification, nothing was stored.  Idempotency (second refresh adds no classification)
    requires running the refresh twice and comparing finding counts.

    Missing surface: API-33 (full pipeline with SIGNAL/CLASSIFY stage), API-42.
    Deferred per task decision G1.
    """
    _probe_api33_api42(stack)
    pytest.skip(
        "NOT RUN (deferred per task decision G1): AC-21 requires the classify stage of the "
        "account-refresh pipeline (API-33 → FETCH → PROCESS → CLASSIFY) to be wired end to "
        "end.  The classification rules and adapters are built (S-SIG-02/S-SIG-04 unit/"
        "contract tests pass) but the pipeline-integration task owns the composed surface.  "
        "Missing surface: API-33 account-refresh pipeline with CLASSIFY stage."
    )


# ---------------------------------------------------------------------------
# AC-22: p_positive thresholds — positive / escalated / NEGATIVE
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-22")
def test_classification_routing_positive_escalated_negative_by_p_positive_threshold(stack):
    """AC-22 (docs/requirements/acceptance.md):

    "Given recorded classifier answers with p_positive 0.9, 0.5 and 0.2 for three pairs,
    when they are routed, then the first is positive without an LLM call for its verdict,
    the second is escalated and carries the LLM's strength, and the third is NEGATIVE with
    no LLM call."

    The routing thresholds live in the scoring settings document
    (docs/architecture/sql-store.md#scoring-settings-document); the escalation rule is in
    docs/architecture/rules.md#signal-classification.  The observable surface is the
    classification.status and finding.decided_by fields returned by API-42.

    Missing surface: API-33 (pipeline with ESCALATE stage), API-42 (findings showing
    decided_by and strength from escalation).  Deferred per task decision G1.
    """
    _probe_api33_api42(stack)
    pytest.skip(
        "NOT RUN (deferred per task decision G1): AC-22 requires the full classify + "
        "escalate stages of the refresh pipeline (API-33), observable through API-42 "
        "(FindingView.decided_by, FindingView.strength).  The routing rules are built "
        "(S-SIG-03 unit/contract tests pass) but the pipeline-integration task owns the "
        "end-to-end surface.  "
        "Missing surface: API-33 account-refresh pipeline with ESCALATE stage, API-42."
    )


# ---------------------------------------------------------------------------
# AC-24: Quote is substring of passage; German docs have quote_en; evidence failure
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-24")
def test_quote_is_substring_of_passage_german_docs_have_quote_en_evidence_failure(stack):
    """AC-24 (docs/requirements/acceptance.md):

    "Given all demo accounts refreshed, when their findings are read, then every quote,
    after collapsing whitespace, is a substring of its passage, every finding from a German
    document has a quote_en and every finding from an English one has none; given a recorded
    evidence answer whose quote is not in the passage on both attempts, then that pair has no
    finding and its classification is EVIDENCE_FAILED."

    Contracts exercised: API-01, API-33, API-35, API-42.
    The quote-in-passage invariant (RULE-02) and the EVIDENCE_FAILED status are observable
    through API-42 (FindingView.quote, FindingView.quote_en,
    FindingView.document.language).  The EVIDENCE_FAILED outcome requires the full signal
    pipeline to run against the recorded evidence-failure fixture.

    Missing surface: API-33 (full pipeline with EVIDENCE stage), API-42 (FindingView).
    Deferred per task decision G1.
    """
    _probe_api33_api42(stack)
    pytest.skip(
        "NOT RUN (deferred per task decision G1): AC-24 requires all demo accounts "
        "refreshed via API-33 in FIXTURE_MODE=replay, then findings read through API-42 "
        "and the quote-in-passage invariant (RULE-02) verified across all returned "
        "FindingView objects.  The evidence rules are built (S-SIG-05/S-SIG-09 unit/"
        "contract tests pass) but the pipeline-integration task owns the composed surface.  "
        "Missing surface: API-33 account-refresh pipeline with EVIDENCE stage, API-42 "
        "(FindingView.quote, FindingView.quote_en, FindingView.document.language)."
    )


# ---------------------------------------------------------------------------
# AC-25: FindingView fields — strength, confidence, decided_by, question revision,
#         option_key for CHOICE, observed_at from publication date or fetch time
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-25")
def test_finding_carries_strength_confidence_decided_by_revision_and_observed_at(stack):
    """AC-25 (docs/requirements/acceptance.md):

    "Given a finding from a document with a publication date and one from a document
    without, when they are read, then each carries strength, confidence, decided_by and
    question revision, a finding of the CHOICE question INCUMBENT_PROVIDER carries the
    option it matched, and observed_at is the publication date for the first and the fetch
    time for the second."

    Contracts exercised: API-01, API-33, API-35, API-42.
    Observable through API-42 FindingView: strength, confidence, decided_by,
    question_revision, option (for CHOICE), observed_at.  The distinction between
    publication-date-sourced and fetch-time-sourced observed_at requires demo documents
    with and without published_at.

    Missing surface: API-33 (full pipeline), API-42 (FindingView).
    Deferred per task decision G1.
    """
    _probe_api33_api42(stack)
    pytest.skip(
        "NOT RUN (deferred per task decision G1): AC-25 requires demo accounts refreshed "
        "via API-33 so that FindingView.observed_at, FindingView.decided_by, "
        "FindingView.strength, FindingView.confidence, FindingView.question_revision and "
        "FindingView.option are populated.  The finding fields are built (S-SIG-06 unit/"
        "contract tests pass) but the pipeline-integration task owns the end-to-end "
        "surface.  "
        "Missing surface: API-33 account-refresh pipeline, API-42 (FindingView fields)."
    )


# ---------------------------------------------------------------------------
# AC-26: Reclassification — RECLASSIFY run supersedes old findings, creates new ones
#         for the changed question only, leaves others unchanged, ends with rescore
# ---------------------------------------------------------------------------

@pytest.mark.ac("AC-26")
def test_reclassify_run_supersedes_old_findings_and_creates_new_at_revision_2(stack):
    """AC-26 (docs/requirements/acceptance.md):

    "Given all demo accounts refreshed and findings for COST_PROGRAM, when an Admin revises
    its text, then the RECLASSIFY run fetches nothing, sets the question's revision-1
    findings SUPERSEDED, creates classifications at revision 2 for that question only,
    leaves every other question's classifications unchanged, and ends by rescoring the
    service."

    Contracts exercised: API-01, API-13 (PATCH question text), API-33, API-35, API-42.
    The RECLASSIFY run is triggered by API-13 (PATCH /services/{id}/questions/{id}) when
    text changes (docs/architecture/interfaces.md).  Observable through API-42: findings
    with status SUPERSEDED vs ACTIVE, question_revision values, and run list.

    Missing surface: API-33 (demo refresh), API-13 (question patch triggering RECLASSIFY),
    API-42 (FindingView.status SUPERSEDED, FindingView.question_revision).
    Deferred per task decision G1.
    """
    _probe_api33_api42(stack)
    pytest.skip(
        "NOT RUN (deferred per task decision G1): AC-26 requires the full reclassification "
        "flow: demo accounts refreshed (API-33), a question-text change (API-13) to "
        "COST_PROGRAM, a RECLASSIFY run completing, and then API-42 returning SUPERSEDED "
        "findings at revision 1 and ACTIVE findings at revision 2.  The reclassification "
        "rules are built (S-SIG-07 unit/integration tests pass) but the pipeline-integration "
        "task owns the end-to-end surface.  "
        "Missing surface: API-33 demo refresh pipeline, API-13 (question text change), "
        "RECLASSIFY run via API-35, API-42 (FindingView.status SUPERSEDED)."
    )
