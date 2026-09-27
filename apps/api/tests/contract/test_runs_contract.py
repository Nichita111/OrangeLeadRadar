"""Contract tests of `API-33` to `API-36`
([Runs and source plug-ins](/architecture/interfaces.md#runs-and-source-plug-ins)), against the
real database with real sign-in."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AccountStatus,
    AuditAction,
    JobStep,
    PipelineRunTrigger,
    SourcePluginCode,
)
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.ingestion import Job
from leadradar.db.models.ingestion import SourcePlugin as SourcePluginRow
from leadradar.runs.enqueue import enqueue_account_rescore
from tests.contract.conftest import _http_client
from tests.integration import factories as f

pytestmark = pytest.mark.contract

RUN_FIELDS = {
    "id",
    "kind",
    "trigger",
    "status",
    "stage",
    "progress",
    "errors",
    "account",
    "service",
    "question",
    "requested_by_name",
    "created_at",
    "started_at",
    "finished_at",
    "ai_cost_eur",
}

MakeAccount = Callable[..., Awaitable[uuid.UUID]]


@pytest.fixture
def make_account(running_app: FastAPI) -> MakeAccount:
    async def make(**overrides: Any) -> uuid.UUID:
        async with running_app.state.engine.begin() as conn:
            account_id: uuid.UUID = await conn.run_sync(
                lambda sync: f.make_account(sync, name="Lufthansa Group", **overrides)
            )
        return account_id

    return make


async def _rescore_run(running_app: FastAPI, user_id: uuid.UUID) -> uuid.UUID:
    async with running_app.state.engine.begin() as conn:
        account_id, service_id = await conn.run_sync(
            lambda sync: (f.make_account(sync), f.make_service(sync))
        )
    async with AsyncSession(running_app.state.engine) as session, session.begin():
        return await enqueue_account_rescore(
            session,
            account_id=account_id,
            service_id=service_id,
            trigger=PipelineRunTrigger.FEEDBACK,
            requested_by=user_id,
            now=datetime.now(tz=UTC),
        )


async def test_refresh_answers_202_with_a_new_run_then_200_with_the_same_run(
    sales_client: httpx.AsyncClient, admin_client: httpx.AsyncClient, make_account: MakeAccount
) -> None:
    account_id = await make_account()

    first = await sales_client.post(f"/api/v1/accounts/{account_id}/refresh")
    second = await admin_client.post(f"/api/v1/accounts/{account_id}/refresh")

    assert first.status_code == 202, first.text
    run = first.json()
    assert set(run) == RUN_FIELDS
    assert run["kind"] == "ACCOUNT_REFRESH"
    assert run["trigger"] == "USER"
    assert run["status"] == "QUEUED"
    assert run["stage"] is None
    assert run["account"] == {"id": str(account_id), "name": "Lufthansa Group"}
    assert run["service"] is None
    assert run["question"] is None
    assert run["requested_by_name"] == "Sales"
    assert run["errors"] == []
    assert run["ai_cost_eur"] == 0
    assert second.status_code == 200
    assert second.json()["id"] == run["id"]


async def test_refresh_of_an_inactive_account_answers_409(
    sales_client: httpx.AsyncClient, make_account: MakeAccount
) -> None:
    account_id = await make_account(status=AccountStatus.INACTIVE)

    response = await sales_client.post(f"/api/v1/accounts/{account_id}/refresh")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_refresh_of_an_unknown_account_answers_404(sales_client: httpx.AsyncClient) -> None:
    response = await sales_client.post(f"/api/v1/accounts/{uuid.uuid4()}/refresh")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_run_routes_refuse_an_anonymous_caller(running_app: FastAPI) -> None:
    async with _http_client(running_app, headers={"X-Requested-With": "XMLHttpRequest"}) as http:
        responses = [
            await http.post(f"/api/v1/accounts/{uuid.uuid4()}/refresh"),
            await http.get("/api/v1/runs"),
            await http.get(f"/api/v1/runs/{uuid.uuid4()}"),
            await http.post(f"/api/v1/runs/{uuid.uuid4()}/cancel"),
        ]
    assert [response.status_code for response in responses] == [401, 401, 401, 401]


async def test_run_detail_answers_the_run_and_404_for_an_unknown_one(
    sales_client: httpx.AsyncClient, make_account: MakeAccount
) -> None:
    account_id = await make_account()
    run_id = (await sales_client.post(f"/api/v1/accounts/{account_id}/refresh")).json()["id"]

    found = await sales_client.get(f"/api/v1/runs/{run_id}")
    missing = await sales_client.get(f"/api/v1/runs/{uuid.uuid4()}")

    assert found.status_code == 200
    assert set(found.json()) == RUN_FIELDS
    assert found.json()["id"] == run_id
    assert missing.status_code == 404


async def test_runs_list_is_a_page_filtered_by_account(
    sales_client: httpx.AsyncClient, make_account: MakeAccount
) -> None:
    account_id = await make_account()
    run_id = (await sales_client.post(f"/api/v1/accounts/{account_id}/refresh")).json()["id"]

    response = await sales_client.get(
        "/api/v1/runs", params={"account_id": str(account_id), "kind": "ACCOUNT_REFRESH"}
    )

    assert response.status_code == 200
    page = response.json()
    assert set(page) == {"items", "page", "page_size", "total"}
    assert (page["page"], page["page_size"], page["total"]) == (1, 50, 1)
    assert [item["id"] for item in page["items"]] == [run_id]


async def test_runs_list_filtered_by_service_and_kind_answers_only_that_service_s_runs_newest_first(
    sales_client: httpx.AsyncClient,
    running_app: FastAPI,
    admin_user: tuple[uuid.UUID, str, str],
) -> None:
    async with running_app.state.engine.begin() as conn:
        account_id, target_service_id, other_service_id = await conn.run_sync(
            lambda sync: (f.make_account(sync), f.make_service(sync), f.make_service(sync))
        )
    async with AsyncSession(running_app.state.engine) as session, session.begin():
        older_run_id = await enqueue_account_rescore(
            session,
            account_id=account_id,
            service_id=target_service_id,
            trigger=PipelineRunTrigger.FEEDBACK,
            requested_by=admin_user[0],
            now=datetime.now(tz=UTC),
        )
    async with AsyncSession(running_app.state.engine) as session, session.begin():
        newer_run_id = await enqueue_account_rescore(
            session,
            account_id=account_id,
            service_id=target_service_id,
            trigger=PipelineRunTrigger.SCORING_ACTIVATION,
            requested_by=admin_user[0],
            now=datetime.now(tz=UTC),
        )
    async with AsyncSession(running_app.state.engine) as session, session.begin():
        await enqueue_account_rescore(
            session,
            account_id=account_id,
            service_id=other_service_id,
            trigger=PipelineRunTrigger.FEEDBACK,
            requested_by=admin_user[0],
            now=datetime.now(tz=UTC),
        )

    response = await sales_client.get(
        "/api/v1/runs", params={"kind": "RESCORE", "service_id": str(target_service_id)}
    )

    assert response.status_code == 200
    page = response.json()
    assert [item["id"] for item in page["items"]] == [str(newer_run_id), str(older_run_id)]
    assert all(item["service"]["id"] == str(target_service_id) for item in page["items"])


async def test_runs_list_refuses_a_page_size_above_the_maximum(
    sales_client: httpx.AsyncClient,
) -> None:
    response = await sales_client.get("/api/v1/runs", params={"page_size": 201})

    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"][0]["field"] == "page_size"


async def test_cancel_answers_the_cancelled_run_then_409(
    sales_client: httpx.AsyncClient, make_account: MakeAccount
) -> None:
    account_id = await make_account()
    run_id = (await sales_client.post(f"/api/v1/accounts/{account_id}/refresh")).json()["id"]

    cancelled = await sales_client.post(f"/api/v1/runs/{run_id}/cancel")
    again = await sales_client.post(f"/api/v1/runs/{run_id}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["finished_at"] is not None
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "CONFLICT"


async def test_only_an_admin_cancels_a_rescore_run(
    running_app: FastAPI,
    sales_client: httpx.AsyncClient,
    admin_client: httpx.AsyncClient,
    admin_user: tuple[uuid.UUID, str, str],
) -> None:
    run_id = await _rescore_run(running_app, admin_user[0])

    refused = await sales_client.post(f"/api/v1/runs/{run_id}/cancel")
    accepted = await admin_client.post(f"/api/v1/runs/{run_id}/cancel")

    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "FORBIDDEN"
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "CANCELLED"


async def test_cancel_of_an_unknown_run_answers_404(admin_client: httpx.AsyncClient) -> None:
    response = await admin_client.post(f"/api/v1/runs/{uuid.uuid4()}/cancel")

    assert response.status_code == 404


# --- API-37, API-38 (AC-32) -------------------------------------------------------------------


@pytest.fixture
async def seeded_plugins(running_app: FastAPI) -> AsyncIterator[None]:
    """One enabled `source_plugin` row per plug-in code, removed again afterwards."""
    async with running_app.state.engine.begin() as conn:
        await conn.execute(delete(SourcePluginRow))
        await conn.run_sync(
            lambda sync: [f.make_source_plugin(sync, code=code) for code in SourcePluginCode]
        )
    yield
    async with running_app.state.engine.begin() as conn:
        await conn.execute(delete(SourcePluginRow))


@pytest.mark.usefixtures("seeded_plugins")
async def test_source_plugins_list_shows_a_keyed_plugin_without_its_key_as_unavailable(
    admin_client: httpx.AsyncClient,
) -> None:
    response = await admin_client.get("/api/v1/source-plugins")

    assert response.status_code == 200
    newsapi = next(entry for entry in response.json() if entry["code"] == "NEWSAPI")
    assert newsapi["needs_key"] is True
    assert newsapi["key_configured"] is False
    assert newsapi["enabled"] is True
    assert newsapi["available"] is False


@pytest.mark.usefixtures("seeded_plugins")
async def test_source_plugin_routes_refuse_sales(sales_client: httpx.AsyncClient) -> None:
    listed = await sales_client.get("/api/v1/source-plugins")
    patched = await sales_client.patch("/api/v1/source-plugins/GDELT", json={"enabled": False})

    assert listed.status_code == 403
    assert patched.status_code == 403


@pytest.mark.usefixtures("seeded_plugins")
async def test_disabling_gdelt_removes_its_fetch_job_from_the_next_refresh(
    admin_client: httpx.AsyncClient, running_app: FastAPI, make_account: MakeAccount
) -> None:
    disabled = await admin_client.patch("/api/v1/source-plugins/GDELT", json={"enabled": False})
    try:
        account_id = await make_account()
        run_id = (await admin_client.post(f"/api/v1/accounts/{account_id}/refresh")).json()["id"]
        async with AsyncSession(running_app.state.engine) as session:
            payloads = (
                await session.execute(
                    select(Job.payload).where(
                        Job.run_id == uuid.UUID(run_id), Job.step == JobStep.FETCH
                    )
                )
            ).scalars()
            fetched = {payload["plugin_code"] for payload in payloads}
    finally:
        await admin_client.patch("/api/v1/source-plugins/GDELT", json={"enabled": True})

    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["available"] is False
    assert fetched
    assert "GDELT" not in fetched


@pytest.mark.usefixtures("seeded_plugins")
@pytest.mark.parametrize("field", ["rate_limit_per_minute", "daily_quota"])
@pytest.mark.parametrize("value", [0, -1])
async def test_source_plugin_update_refuses_a_limit_of_zero_or_below(
    admin_client: httpx.AsyncClient, field: str, value: int
) -> None:
    response = await admin_client.patch("/api/v1/source-plugins/GDELT", json={field: value})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION"
    assert body["error"]["details"]["fields"][0]["field"] == field

    unchanged = await admin_client.get("/api/v1/source-plugins")
    gdelt = next(entry for entry in unchanged.json() if entry["code"] == "GDELT")
    assert gdelt["rate_limit_per_minute"] == 60
    assert gdelt["daily_quota"] is None


@pytest.mark.usefixtures("seeded_plugins")
async def test_source_plugin_update_clears_the_daily_quota_when_sent_null_and_keeps_it_when_absent(
    admin_client: httpx.AsyncClient,
) -> None:
    quota_set = await admin_client.patch(
        "/api/v1/source-plugins/GDELT", json={"daily_quota": 500}
    )
    kept = await admin_client.patch(
        "/api/v1/source-plugins/GDELT", json={"rate_limit_per_minute": 45}
    )
    cleared = await admin_client.patch("/api/v1/source-plugins/GDELT", json={"daily_quota": None})

    assert quota_set.status_code == 200
    assert quota_set.json()["daily_quota"] == 500
    assert kept.status_code == 200
    assert kept.json()["daily_quota"] == 500
    assert kept.json()["rate_limit_per_minute"] == 45
    assert cleared.status_code == 200
    assert cleared.json()["daily_quota"] is None


async def _plugin_updated_rows(running_app: FastAPI) -> list[AuditEvent]:
    async with AsyncSession(running_app.state.engine) as session:
        return list(
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.action == AuditAction.PLUGIN_UPDATED,
                        AuditEvent.payload["code"].astext == "GDELT",
                    )
                )
            ).scalars()
        )


@pytest.mark.usefixtures("seeded_plugins")
async def test_source_plugin_update_of_a_limit_returns_the_plugin_and_writes_one_audit_row(
    admin_client: httpx.AsyncClient, running_app: FastAPI
) -> None:
    before = await _plugin_updated_rows(running_app)

    response = await admin_client.patch(
        "/api/v1/source-plugins/GDELT", json={"rate_limit_per_minute": 45}
    )

    assert response.status_code == 200
    assert response.json()["rate_limit_per_minute"] == 45
    after = await _plugin_updated_rows(running_app)
    assert len(after) == len(before) + 1
    assert after[-1].payload == {"code": "GDELT", "rate_limit_per_minute": 45}


@pytest.mark.usefixtures("seeded_plugins")
async def test_an_unchanged_source_plugin_value_writes_no_audit_row(
    admin_client: httpx.AsyncClient, running_app: FastAPI
) -> None:
    before = await _plugin_updated_rows(running_app)

    response = await admin_client.patch(
        "/api/v1/source-plugins/GDELT", json={"rate_limit_per_minute": 60}
    )

    assert response.status_code == 200
    after = await _plugin_updated_rows(running_app)
    assert len(after) == len(before)


@pytest.mark.usefixtures("seeded_plugins")
async def test_source_plugin_update_without_the_csrf_header_is_refused_403(
    running_app: FastAPI,
) -> None:
    async with _http_client(running_app) as http:
        response = await http.patch("/api/v1/source-plugins/GDELT", json={"enabled": False})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
