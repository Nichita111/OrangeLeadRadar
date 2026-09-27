"""API-11, API-12 and API-13 expose the run queued by a question change."""

from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.contract


async def test_question_write_returns_its_run_and_reads_return_null(
    admin_client: httpx.AsyncClient,
) -> None:
    suffix = uuid.uuid4().hex[:8].upper()
    service = await admin_client.post(
        "/api/v1/services",
        json={
            "code": f"SERVICE_{suffix}",
            "name": f"Service {suffix}",
            "description": "A service",
            "value_proposition": "A proposition",
        },
    )
    assert service.status_code == 200, service.text
    service_id = service.json()["id"]
    created = await admin_client.post(
        f"/api/v1/services/{service_id}/questions",
        json={
            "key": "NEW_SIGNAL",
            "text": "Does it have a signal?",
            "answer_type": "YES_NO",
            "polarity": "POSITIVE",
            "source_types": ["NEWS"],
        },
    )
    assert created.status_code == 200, created.text
    first_run = uuid.UUID(created.json()["run_id"])
    question_id = created.json()["id"]
    listed = await admin_client.get(f"/api/v1/services/{service_id}/questions")
    assert listed.status_code == 200
    assert listed.json()[0]["run_id"] is None

    revised = await admin_client.patch(
        f"/api/v1/questions/{question_id}", json={"text": "Does it have a revised signal?"}
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["revision"] == 2
    assert uuid.UUID(revised.json()["run_id"]) != first_run
    hints = await admin_client.patch(
        f"/api/v1/questions/{question_id}", json={"hint_terms": ["new"]}
    )
    assert hints.status_code == 200, hints.text
    assert hints.json()["run_id"] is None
