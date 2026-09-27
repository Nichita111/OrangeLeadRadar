"""Contract tests of `API-60` `GET /audit`
([Audit and health](/architecture/interfaces.md#audit-and-health);
[`AuditEntry`](/architecture/interfaces.md#auditentry); `AC-56`).

Every row a test needs is written directly with `factories.make_audit_event`, never through a
capability, so the scenario names exactly the kinds, actions, actors, entities and dates the
criterion describes. `audit_event` is append-only and shared by the whole contract session, so
every scenario is anchored to a `pipeline_run` row this test alone created and filters by its
`run_id`, which the assertions never see polluted by another test's rows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI

from leadradar.core.enums import AuditAction, AuditEventKind
from tests.integration import factories as f

pytestmark = pytest.mark.contract

ENTRY_FIELDS = {
    "id",
    "occurred_at",
    "kind",
    "action",
    "entity_type",
    "entity_id",
    "run_id",
    "request_id",
    "payload",
    "actor_name",
}


async def _run(app: FastAPI) -> uuid.UUID:
    async with app.state.engine.begin() as conn:
        run_id: uuid.UUID = await conn.run_sync(f.make_pipeline_run)
    return run_id


async def _event(app: FastAPI, **overrides: object) -> uuid.UUID:
    async with app.state.engine.begin() as conn:
        event_id: uuid.UUID = await conn.run_sync(
            lambda sync: f.make_audit_event(sync, **overrides)
        )
    return event_id


async def test_filtering_by_kind_ai_call_and_a_run_returns_only_that_runs_ai_calls_newest_first(
    running_app: FastAPI, admin_client: httpx.AsyncClient
) -> None:
    run_id = await _run(running_app)
    other_run_id = await _run(running_app)
    base = datetime.now(tz=UTC) - timedelta(minutes=10)

    first_call = await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.AI_CALL,
        action=AuditAction.AI_CALL.value,
        occurred_at=base,
    )
    second_call = await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.AI_CALL,
        action=AuditAction.AI_CALL.value,
        occurred_at=base + timedelta(minutes=1),
    )
    await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.RUN,
        action=AuditAction.RUN_FINISHED.value,
        occurred_at=base + timedelta(minutes=2),
    )
    await _event(
        running_app,
        run_id=other_run_id,
        kind=AuditEventKind.AI_CALL,
        action=AuditAction.AI_CALL.value,
        occurred_at=base,
    )

    response = await admin_client.get(
        "/api/v1/audit", params={"kind": "AI_CALL", "run_id": str(run_id)}
    )

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert [item["id"] for item in page["items"]] == [str(second_call), str(first_call)]
    assert {item["kind"] for item in page["items"]} == {"AI_CALL"}


async def test_repeated_kind_matches_any_of_the_kinds(
    running_app: FastAPI, admin_client: httpx.AsyncClient
) -> None:
    run_id = await _run(running_app)
    config_id = await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.CONFIG,
        action=AuditAction.SERVICE_CREATED.value,
    )
    run_row_id = await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.RUN,
        action=AuditAction.RUN_REQUESTED.value,
    )
    await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.AUTH,
        action=AuditAction.LOGIN_SUCCEEDED.value,
    )

    response = await admin_client.get(
        "/api/v1/audit", params={"kind": ["CONFIG", "RUN"], "run_id": str(run_id)}
    )

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert {item["id"] for item in page["items"]} == {str(config_id), str(run_row_id)}
    assert {item["kind"] for item in page["items"]} == {"CONFIG", "RUN"}


async def test_action_actor_entity_and_date_range_each_narrow_the_entries(
    running_app: FastAPI, admin_client: httpx.AsyncClient
) -> None:
    run_id = await _run(running_app)
    async with running_app.state.engine.begin() as conn:
        actor_id: uuid.UUID = await conn.run_sync(f.make_app_user)
    entity_id = uuid.uuid4()
    base = datetime.now(tz=UTC) - timedelta(minutes=10)

    the_one = await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.CONFIG,
        action=AuditAction.SERVICE_CREATED.value,
        actor_id=actor_id,
        entity_id=entity_id,
        occurred_at=base,
    )
    await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.CONFIG,
        action=AuditAction.SERVICE_UPDATED.value,
        actor_id=None,
        entity_id=uuid.uuid4(),
        occurred_at=base + timedelta(minutes=1),
    )
    await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.RUN,
        action=AuditAction.RUN_REQUESTED.value,
        actor_id=None,
        entity_id=uuid.uuid4(),
        occurred_at=base + timedelta(minutes=2),
    )

    by_action = await admin_client.get(
        "/api/v1/audit", params={"run_id": str(run_id), "action": "SERVICE_CREATED"}
    )
    by_actor = await admin_client.get(
        "/api/v1/audit", params={"run_id": str(run_id), "actor_id": str(actor_id)}
    )
    by_entity = await admin_client.get(
        "/api/v1/audit", params={"run_id": str(run_id), "entity_id": str(entity_id)}
    )
    by_range = await admin_client.get(
        "/api/v1/audit",
        params={
            "run_id": str(run_id),
            "from": base.isoformat(),
            "to": (base + timedelta(seconds=30)).isoformat(),
        },
    )

    for response in (by_action, by_actor, by_entity, by_range):
        assert response.status_code == 200
        page = response.json()
        assert page["total"] == 1
        assert page["items"][0]["id"] == str(the_one)


async def test_without_from_only_the_last_default_range_days_are_returned(
    running_app: FastAPI, admin_client: httpx.AsyncClient
) -> None:
    run_id = await _run(running_app)
    settings = running_app.state.settings
    now = datetime.now(tz=UTC)
    just_inside = now - timedelta(days=settings.audit_default_range_days) + timedelta(hours=1)
    just_outside = now - timedelta(days=settings.audit_default_range_days) - timedelta(hours=1)

    inside_id = await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.RUN,
        action=AuditAction.RUN_FINISHED.value,
        occurred_at=just_inside,
    )
    outside_id = await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.RUN,
        action=AuditAction.RUN_FINISHED.value,
        occurred_at=just_outside,
    )

    without_from = await admin_client.get("/api/v1/audit", params={"run_id": str(run_id)})
    with_from = await admin_client.get(
        "/api/v1/audit",
        params={"run_id": str(run_id), "from": (now - timedelta(days=365)).isoformat()},
    )

    assert without_from.status_code == 200 and with_from.status_code == 200
    assert [item["id"] for item in without_from.json()["items"]] == [str(inside_id)]
    assert {item["id"] for item in with_from.json()["items"]} == {str(inside_id), str(outside_id)}


async def test_an_entry_has_the_audit_entry_shape_with_actor_name_null_for_the_system(
    running_app: FastAPI, admin_client: httpx.AsyncClient, admin_user: tuple[uuid.UUID, str, str]
) -> None:
    run_id = await _run(running_app)
    admin_id, _, _ = admin_user
    by_user = await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.CONFIG,
        action=AuditAction.SERVICE_CREATED.value,
        actor_id=admin_id,
        payload={"code": "A_CODE"},
    )
    by_system = await _event(
        running_app,
        run_id=run_id,
        kind=AuditEventKind.RUN,
        action=AuditAction.RUN_FINISHED.value,
        actor_id=None,
    )

    response = await admin_client.get("/api/v1/audit", params={"run_id": str(run_id)})

    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert set(items[str(by_user)]) == ENTRY_FIELDS
    assert items[str(by_user)]["actor_name"] == "Admin"
    assert items[str(by_user)]["payload"] == {"code": "A_CODE"}
    assert items[str(by_system)]["actor_name"] is None


async def test_an_unknown_kind_is_refused_422_naming_kind(admin_client: httpx.AsyncClient) -> None:
    response = await admin_client.get("/api/v1/audit", params={"kind": "NOT_A_KIND"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION"
    assert any(entry["field"] == "/kind/0" for entry in body["error"]["details"]["fields"])
