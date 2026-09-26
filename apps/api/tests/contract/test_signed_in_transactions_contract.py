"""Contract tests of routes whose capability function writes or reads in the request's one
transaction, through a real sign-in: authentication already opened that transaction on the
session, so the function must not open a second one ([api Design]
(/architecture/services/api.md#design) Transactions)."""

from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.contract


async def test_lead_feedback_for_an_unscored_account_answers_404_not_500(
    sales_client: httpx.AsyncClient,
) -> None:
    response = await sales_client.post(
        f"/api/v1/accounts/{uuid.uuid4()}/scores/{uuid.uuid4()}/feedback",
        json={"verdict": "RELEVANT"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_finding_feedback_for_an_unknown_finding_answers_404_not_500(
    sales_client: httpx.AsyncClient,
) -> None:
    response = await sales_client.post(
        f"/api/v1/findings/{uuid.uuid4()}/feedback", json={"verdict": "CORRECT"}
    )

    assert response.status_code == 404


async def test_impact_answers_200_for_a_signed_in_admin(admin_client: httpx.AsyncClient) -> None:
    response = await admin_client.get("/api/v1/impact")

    assert response.status_code == 200
