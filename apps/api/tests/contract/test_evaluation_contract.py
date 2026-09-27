"""Contract tests of `API-50` to `API-55` and `API-77`
([Evaluation contracts](/architecture/interfaces.md#evaluation-contracts)), against the real
database with real sign-in. The `401`/`403` of every route is covered generically by
`test_roles_matrix_contract.py`; CSRF by `test_csrf_contract.py`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import Connection

from leadradar.api.authentication import current_user
from leadradar.core.enums import (
    AppUserRole,
    DocumentSourceType,
    DocumentTriageOutcome,
    EvaluationItemOrigin,
    FindingStrength,
    PipelineRunKind,
    PipelineRunStatus,
)
from leadradar.core.impact import ImpactReport
from leadradar.db.models.identity import AppUser
from leadradar.db.session import get_session
from tests.integration import factories as f

pytestmark = pytest.mark.contract


async def _label_queue_arrangement(running_app: FastAPI) -> dict[str, uuid.UUID]:
    """A service, an active question, an active account, and a `KEPT` document with two
    passages neither classified: qualifies for the label queue's `NOT_SELECTED` stratum."""
    async with running_app.state.engine.begin() as conn:

        def build(sync: Connection) -> dict[str, uuid.UUID]:
            service_id = f.make_service(sync)
            question_id = f.make_signal_question(sync, service_id)
            account_id = f.make_account(sync)
            run_id = f.make_pipeline_run(sync)
            document_id = f.make_document(
                sync,
                run_id,
                account_id=account_id,
                source_type=DocumentSourceType.NEWS,
                text="A long document with two passages.",
            )
            f.make_document_triage(
                sync,
                document_id,
                outcome=DocumentTriageOutcome.KEPT,
                service_relevance={str(service_id): 0.9},
            )
            chunk_id = f.make_chunk(sync, document_id, ordinal=0, text="First passage.")
            f.make_chunk(sync, document_id, ordinal=1, text="Second passage.")
            return {
                "service": service_id,
                "question": question_id,
                "account": account_id,
                "document": document_id,
                "chunk": chunk_id,
            }

        result: dict[str, uuid.UUID] = await conn.run_sync(build)
        return result


_REPORT = ImpactReport(
    period_days=30,
    accounts_refreshed=3,
    refreshes=4,
    cost_per_refresh_eur=1.25,
    minutes_per_refresh=6.5,
    findings_created=7,
    precision=0.91,
    labelled_items=250,
    manual_minutes_per_account=120,
    manual_hours_replaced=6.0,
)


async def test_impact_answers_200_with_exactly_the_shape_of_impact(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_read_impact(*args: object, **kwargs: object) -> ImpactReport:
        return _REPORT

    monkeypatch.setattr("leadradar.api.evaluation.read_impact", fake_read_impact)
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: AppUser(
        display_name="Ada", role=AppUserRole.ADMIN
    )

    response = await client.get("/api/v1/impact")

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(current_user, None)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "period_days",
        "accounts_refreshed",
        "refreshes",
        "cost_per_refresh_eur",
        "minutes_per_refresh",
        "findings_created",
        "precision",
        "labelled_items",
        "manual_minutes_per_account",
        "manual_hours_replaced",
    }
    assert isinstance(body["period_days"], int)
    assert isinstance(body["accounts_refreshed"], int)
    assert isinstance(body["refreshes"], int)
    assert isinstance(body["cost_per_refresh_eur"], float)
    assert isinstance(body["minutes_per_refresh"], float)
    assert isinstance(body["findings_created"], int)
    assert isinstance(body["precision"], float)
    assert isinstance(body["labelled_items"], int)
    assert isinstance(body["manual_minutes_per_account"], int)
    assert isinstance(body["manual_hours_replaced"], float)


async def test_impact_reports_null_cost_precision_and_labelled_items_without_runs_or_a_pass(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_report = ImpactReport(
        period_days=30,
        accounts_refreshed=0,
        refreshes=0,
        cost_per_refresh_eur=None,
        minutes_per_refresh=None,
        findings_created=0,
        precision=None,
        labelled_items=None,
        manual_minutes_per_account=120,
        manual_hours_replaced=0.0,
    )

    async def fake_read_impact(*args: object, **kwargs: object) -> ImpactReport:
        return empty_report

    monkeypatch.setattr("leadradar.api.evaluation.read_impact", fake_read_impact)
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: AppUser(
        display_name="Ada", role=AppUserRole.ADMIN
    )

    response = await client.get("/api/v1/impact")

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(current_user, None)
    assert response.status_code == 200
    body = response.json()
    assert body["cost_per_refresh_eur"] is None
    assert body["minutes_per_refresh"] is None
    assert body["precision"] is None
    assert body["labelled_items"] is None


LABEL_TASK_FIELDS = {
    "chunk_id",
    "passage_text",
    "question",
    "question_revision",
    "account",
    "document",
}
EVALUATION_ITEM_FIELDS = {
    "id",
    "chunk_id",
    "question_id",
    "question_revision",
    "created_at",
    "question_key",
    "expected_strength",
    "origin",
    "status",
    "labelled_by_name",
}


async def test_label_queue_requires_service_id_and_answers_404_for_unknown_service(
    sales_client: httpx.AsyncClient,
) -> None:
    missing_param = await sales_client.get("/api/v1/evaluation/label-queue")
    unknown_service = await sales_client.get(
        "/api/v1/evaluation/label-queue", params={"service_id": str(uuid.uuid4())}
    )

    assert missing_param.status_code == 422
    assert unknown_service.status_code == 404
    assert unknown_service.json()["error"]["code"] == "NOT_FOUND"


async def test_label_queue_shape_never_carries_the_classifiers_answer(
    running_app: FastAPI, sales_client: httpx.AsyncClient
) -> None:
    ids = await _label_queue_arrangement(running_app)

    response = await sales_client.get(
        "/api/v1/evaluation/label-queue", params={"service_id": str(ids["service"])}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"tasks", "active_items", "min_items"}
    # Both of the document's two passages are unclassified and qualify (`NOT_SELECTED`).
    assert len(body["tasks"]) == 2
    task = body["tasks"][0]
    assert set(task) == LABEL_TASK_FIELDS
    assert "p_positive" not in task
    assert "strength" not in task
    assert "answer" not in task
    assert set(task["question"]) == {"id", "key", "text", "answer_type", "options", "polarity"}


async def test_label_item_writes_a_manual_label_and_answers_evaluationitem(
    running_app: FastAPI, sales_client: httpx.AsyncClient
) -> None:
    ids = await _label_queue_arrangement(running_app)

    response = await sales_client.post(
        "/api/v1/evaluation/items",
        json={
            "chunk_id": str(ids["chunk"]),
            "question_id": str(ids["question"]),
            "question_revision": 1,
            "expected_strength": "STRONG",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == EVALUATION_ITEM_FIELDS
    assert body["expected_strength"] == "STRONG"
    assert body["origin"] == "MANUAL"
    assert body["status"] == "ACTIVE"


async def test_label_item_answers_404_for_an_unknown_chunk_or_question(
    running_app: FastAPI, sales_client: httpx.AsyncClient
) -> None:
    ids = await _label_queue_arrangement(running_app)

    unknown_chunk = await sales_client.post(
        "/api/v1/evaluation/items",
        json={
            "chunk_id": str(uuid.uuid4()),
            "question_id": str(ids["question"]),
            "question_revision": 1,
            "expected_strength": "WEAK",
        },
    )
    unknown_question = await sales_client.post(
        "/api/v1/evaluation/items",
        json={
            "chunk_id": str(ids["chunk"]),
            "question_id": str(uuid.uuid4()),
            "question_revision": 1,
            "expected_strength": "WEAK",
        },
    )

    assert unknown_chunk.status_code == 404
    assert unknown_question.status_code == 404


async def test_label_item_answers_409_when_the_revision_is_not_current(
    running_app: FastAPI, sales_client: httpx.AsyncClient
) -> None:
    ids = await _label_queue_arrangement(running_app)

    response = await sales_client.post(
        "/api/v1/evaluation/items",
        json={
            "chunk_id": str(ids["chunk"]),
            "question_id": str(ids["question"]),
            "question_revision": 2,
            "expected_strength": "WEAK",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_label_item_answers_422_for_an_unknown_field_or_a_bad_strength(
    running_app: FastAPI, sales_client: httpx.AsyncClient
) -> None:
    ids = await _label_queue_arrangement(running_app)

    unknown_field = await sales_client.post(
        "/api/v1/evaluation/items",
        json={
            "chunk_id": str(ids["chunk"]),
            "question_id": str(ids["question"]),
            "question_revision": 1,
            "expected_strength": "WEAK",
            "surprise": True,
        },
    )
    bad_strength = await sales_client.post(
        "/api/v1/evaluation/items",
        json={
            "chunk_id": str(ids["chunk"]),
            "question_id": str(ids["question"]),
            "question_revision": 1,
            "expected_strength": "NOT_A_STRENGTH",
        },
    )

    assert unknown_field.status_code == 422
    assert bad_strength.status_code == 422


async def test_list_items_is_a_page_filtered_by_question_and_origin(
    running_app: FastAPI, sales_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    ids = await _label_queue_arrangement(running_app)
    labelled = await sales_client.post(
        "/api/v1/evaluation/items",
        json={
            "chunk_id": str(ids["chunk"]),
            "question_id": str(ids["question"]),
            "question_revision": 1,
            "expected_strength": "MEDIUM",
        },
    )
    item_id = labelled.json()["id"]

    response = await admin_client.get(
        "/api/v1/evaluation/items",
        params={"question_id": str(ids["question"]), "origin": "MANUAL"},
    )

    assert response.status_code == 200
    page = response.json()
    assert set(page) == {"items", "page", "page_size", "total"}
    assert [item["id"] for item in page["items"]] == [item_id]

    no_match = await admin_client.get(
        "/api/v1/evaluation/items", params={"origin": "FINDING_FEEDBACK"}
    )
    assert no_match.json()["total"] == 0


async def test_evaluation_run_answers_202_then_200_with_the_same_run(
    admin_client: httpx.AsyncClient,
) -> None:
    first = await admin_client.post("/api/v1/evaluation/runs")
    second = await admin_client.post("/api/v1/evaluation/runs")

    assert first.status_code == 202, first.text
    assert first.json()["kind"] == "EVALUATION"
    assert first.json()["status"] == "QUEUED"
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


async def test_evaluation_results_lists_newest_first_with_the_summary_shape(
    running_app: FastAPI, admin_client: httpx.AsyncClient
) -> None:
    async with running_app.state.engine.begin() as conn:

        def build(sync: Connection) -> tuple[uuid.UUID, uuid.UUID]:
            older_run = f.make_pipeline_run(
                sync, kind=PipelineRunKind.EVALUATION, status=PipelineRunStatus.SUCCEEDED
            )
            newer_run = f.make_pipeline_run(
                sync, kind=PipelineRunKind.EVALUATION, status=PipelineRunStatus.SUCCEEDED
            )
            f.make_evaluation_result(
                sync,
                older_run,
                metrics={"precision": 0.5, "recall": 0.6, "escalation_rate": 0.1},
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            f.make_evaluation_result(
                sync,
                newer_run,
                metrics={"precision": 0.9, "recall": 0.8, "escalation_rate": 0.2},
                created_at=datetime(2026, 6, 1, tzinfo=UTC),
            )
            return older_run, newer_run

        older_run, newer_run = await conn.run_sync(build)

    response = await admin_client.get("/api/v1/evaluation/results")

    assert response.status_code == 200
    results = response.json()
    ids = [result["run_id"] for result in results]
    assert ids.index(str(newer_run)) < ids.index(str(older_run))
    first = results[0]
    assert set(first) == {
        "run_id",
        "created_at",
        "classifier",
        "items",
        "passed",
        "precision",
        "recall",
        "escalation_rate",
    }


async def test_evaluation_result_detail_enriches_errors_and_answers_404(
    running_app: FastAPI,
    admin_client: httpx.AsyncClient,
    admin_user: tuple[uuid.UUID, str, str],
) -> None:
    ids = await _label_queue_arrangement(running_app)
    admin_id = admin_user[0]

    async with running_app.state.engine.begin() as conn:

        def build(sync: Connection) -> uuid.UUID:
            item_id = f.make_evaluation_item(
                sync,
                ids["chunk"],
                ids["question"],
                labelled_by=admin_id,
                expected_strength=FindingStrength.STRONG,
                origin=EvaluationItemOrigin.MANUAL,
            )
            run_id = f.make_pipeline_run(
                sync, kind=PipelineRunKind.EVALUATION, status=PipelineRunStatus.SUCCEEDED
            )
            f.make_evaluation_result(
                sync,
                run_id,
                items=1,
                metrics={
                    "precision": 0.0,
                    "recall": None,
                    "escalation_rate": None,
                    "errors": [
                        {
                            "item_id": str(item_id),
                            "expected": "STRONG",
                            "predicted": "NONE",
                            "p_positive": 0.1,
                            "escalated": False,
                        }
                    ],
                },
            )
            return run_id

        run_id = await conn.run_sync(build)

    response = await admin_client.get(f"/api/v1/evaluation/results/{run_id}")
    missing = await admin_client.get(f"/api/v1/evaluation/results/{uuid.uuid4()}")

    assert response.status_code == 200, response.text
    body = response.json()
    error_entry = body["metrics"]["errors"][0]
    assert error_entry["question_key"] is not None
    assert error_entry["passage_text"] == "First passage."
    assert set(error_entry["document"]) == {"title", "url"}
    assert missing.status_code == 404
