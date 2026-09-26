"""Unit test of [Audit actions](/architecture/sql-store.md#audit-actions):
`core.enums.AuditEventAction` holds exactly the closed vocabulary the table lists."""

from __future__ import annotations

import pytest

from leadradar.core.enums import AuditEventAction

pytestmark = pytest.mark.unit

_TABLE_ACTIONS = {
    "LOGIN_SUCCEEDED",
    "LOGIN_FAILED",
    "LOGOUT",
    "USER_CREATED",
    "USER_UPDATED",
    "SERVICE_CREATED",
    "SERVICE_UPDATED",
    "INDUSTRY_CREATED",
    "INDUSTRY_UPDATED",
    "MARKET_CREATED",
    "MARKET_UPDATED",
    "QUESTION_CREATED",
    "QUESTION_UPDATED",
    "SCORING_DRAFT_SAVED",
    "SCORING_ACTIVATED",
    "PLUGIN_UPDATED",
    "ACCOUNT_CREATED",
    "ACCOUNT_UPDATED",
    "ACCOUNTS_IMPORTED",
    "CANDIDATE_ACCEPTED",
    "CANDIDATE_REJECTED",
    "CONTACT_CREATED",
    "CONTACT_UPDATED",
    "CONTACT_ERASED",
    "RUN_REQUESTED",
    "RUN_FINISHED",
    "RUN_CANCELLED",
    "OVERRIDE_CREATED",
    "OVERRIDE_REVOKED",
    "LEAD_FEEDBACK_GIVEN",
    "FINDING_FEEDBACK_GIVEN",
    "ITEM_LABELLED",
    "DRAFT_CREATED",
    "DRAFT_UPDATED",
    "DRAFT_EXPORTED",
    "CRM_PUSHED",
    "AI_CALL",
}


def test_holds_exactly_the_actions_of_the_audit_actions_table() -> None:
    assert {member.value for member in AuditEventAction} == _TABLE_ACTIONS
