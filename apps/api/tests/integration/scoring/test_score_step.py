"""Integration tests for the activation transaction of `API-18`.

Uses a real PostgreSQL container (via testcontainers): rows are seeded with direct SQL on the
`async_connection` fixture's transaction, which the fixture rolls back, so nothing outlives a
test. No mocks; assertions are on the database state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from leadradar.configuration.errors import DraftInvalid
from leadradar.logs import request_id_var
from leadradar.scoring.activate import activate_scoring_config
from leadradar.scoring.errors import NotADraft

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_service(conn: Connection) -> uuid.UUID:
    service_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO service (id, code, name, description, value_proposition, status, "
            "created_at, updated_at) "
            "VALUES (:id, :code, :name, :desc, :vp, 'ACTIVE', now(), now())"
        ),
        {
            "id": service_id,
            "code": f"SVC_{service_id.hex[:6].upper()}",
            "name": f"Test Service {service_id.hex[:6]}",
            "desc": "Test service.",
            "vp": "Test VP.",
        },
    )
    return service_id


def _insert_scoring_config(
    conn: Connection,
    service_id: uuid.UUID,
    status: str = "DRAFT",
    version: int = 1,
) -> uuid.UUID:
    config_id = uuid.uuid4()
    settings = {
        "fit_weight": 0.4,
        "intent_weight": 0.6,
        "min_fit": 40,
        "hot_threshold": 70,
        "warm_threshold": 40,
        "weight_values": {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0},
        "strength_values": {"WEAK": 0.5, "MEDIUM": 0.75, "STRONG": 1.0},
        "default_half_life_days": {
            "NEWS": 90,
            "COMPANY_PUBLICATION": 365,
            "JOB_POSTING": 60,
            "COMPANY_PROFILE": 365,
        },
        "min_decay": 0.05,
        "negative_factor": 1.0,
        "intent_saturation": 0.5,
        "unknown_match": 0.5,
        "icp_criteria": [],
        "questions": [],
        "disqualifiers": [],
    }
    import json

    conn.execute(
        text(
            "INSERT INTO scoring_config (id, service_id, version, status, settings, change_note, "
            "activated_at, activated_by, created_at, updated_at) "
            "VALUES (:id, :service_id, :version, :status, CAST(:settings AS jsonb), "
            "NULL, NULL, NULL, now(), now())"
        ),
        {
            "id": config_id,
            "service_id": service_id,
            "version": version,
            "status": status,
            "settings": json.dumps(settings),
        },
    )
    return config_id


def _insert_user(conn: Connection) -> uuid.UUID:
    user_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO app_user (id, email, display_name, role, status, password_hash, "
            "failed_logins, created_at, updated_at) "
            "VALUES (:id, :email, :name, 'ADMIN', 'ACTIVE', 'x', 0, now(), now())"
        ),
        {"id": user_id, "email": f"test_{user_id.hex[:8]}@test.com", "name": "Test Admin"},
    )
    return user_id


def _insert_pipeline_run(
    conn: Connection,
    service_id: uuid.UUID,
    actor_id: uuid.UUID,
    kind: str = "RESCORE",
    status: str = "QUEUED",
) -> uuid.UUID:
    run_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO pipeline_run (id, kind, trigger, account_id, service_id, question_id, "
            "status, stage, progress, errors, requested_by, started_at, finished_at, "
            "created_at, updated_at) "
            "VALUES (:id, :kind, 'SCORING_ACTIVATION', NULL, :service_id, NULL, :status, NULL, "
            "'{}'::jsonb, '[]'::jsonb, :actor, NULL, NULL, now(), now())"
        ),
        {"id": run_id, "kind": kind, "service_id": service_id, "status": status, "actor": actor_id},
    )
    return run_id


def _insert_job(
    conn: Connection,
    run_id: uuid.UUID,
    step: str = "SCORE",
    status: str = "READY",
    priority: int = 3,
    attempts: int = 0,
) -> uuid.UUID:
    job_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO job (id, run_id, step, payload, status, priority, attempts, "
            "not_before, locked_by, locked_at, last_error, created_at, updated_at) "
            "VALUES (:id, :run_id, :step, '{}'::jsonb, :status, :priority, :attempts, "
            "now(), NULL, NULL, NULL, now(), now())"
        ),
        {
            "id": job_id,
            "run_id": run_id,
            "step": step,
            "status": status,
            "priority": priority,
            "attempts": attempts,
        },
    )
    return job_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_activation_sets_draft_to_active_and_retires_previous(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    """Activation: draft to ACTIVE, previous ACTIVE to RETIRED, one run and job, 2 audit rows."""
    service_id = await async_connection.run_sync(_insert_service)
    actor_id = await async_connection.run_sync(_insert_user)
    prev_config_id = await async_connection.run_sync(
        lambda c: _insert_scoring_config(c, service_id, status="ACTIVE", version=1)
    )
    draft_config_id = await async_connection.run_sync(
        lambda c: _insert_scoring_config(c, service_id, status="DRAFT", version=2)
    )

    current_time = datetime(2026, 9, 26, 12, tzinfo=UTC)
    token = request_id_var.set("req-1")
    try:
        await activate_scoring_config(
            async_session,
            config_id=draft_config_id,
            actor_id=actor_id,
            change_note="v2 go live",
            now=current_time,
        )
    finally:
        request_id_var.reset(token)

    async def scalar(sql: str, **params: object) -> object:
        return (await async_session.execute(text(sql), params)).scalar_one()

    status_of = "SELECT status FROM scoring_config WHERE id = :id"
    assert await scalar(status_of, id=draft_config_id) == "ACTIVE"
    assert await scalar(status_of, id=prev_config_id) == "RETIRED"
    assert (
        await scalar(
            "SELECT COUNT(*) FROM pipeline_run WHERE service_id = :sid AND kind = 'RESCORE'",
            sid=service_id,
        )
        == 1
    )
    assert (
        await scalar(
            "SELECT COUNT(*) FROM job j JOIN pipeline_run pr ON j.run_id = pr.id "
            "WHERE pr.service_id = :sid AND j.step = 'SCORE'",
            sid=service_id,
        )
        == 1
    )
    audit_count = await scalar(
        "SELECT COUNT(*) FROM audit_event "
        "WHERE action IN ('SCORING_ACTIVATED', 'RUN_REQUESTED') AND actor_id = :actor",
        actor=actor_id,
    )
    assert audit_count == 2
    audit_rows = (
        await async_session.execute(
            text(
                "SELECT request_id, occurred_at FROM audit_event WHERE actor_id = :actor "
                "AND action IN ('SCORING_ACTIVATED', 'RUN_REQUESTED')"
            ),
            {"actor": actor_id},
        )
    ).all()
    assert all(row.request_id == "req-1" and row.occurred_at == current_time for row in audit_rows)


async def test_activation_revalidates_a_draft_before_writing(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    service_id = await async_connection.run_sync(_insert_service)
    actor_id = await async_connection.run_sync(_insert_user)
    draft_id = await async_connection.run_sync(
        lambda c: _insert_scoring_config(c, service_id, status="DRAFT")
    )
    await async_session.execute(
        text(
            "UPDATE scoring_config SET settings = jsonb_set(settings, '{fit_weight}', '0.9') "
            "WHERE id = :id"
        ),
        {"id": draft_id},
    )

    with pytest.raises(DraftInvalid):
        await activate_scoring_config(
            async_session,
            config_id=draft_id,
            actor_id=actor_id,
            change_note="invalid weights",
            now=datetime(2026, 9, 26, 12, tzinfo=UTC),
        )
    assert (
        await async_session.execute(
            text("SELECT status FROM scoring_config WHERE id = :id"), {"id": draft_id}
        )
    ).scalar_one() == "DRAFT"


async def test_activation_of_non_draft_raises(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    """Activating an ACTIVE config raises NotADraft."""
    service_id = await async_connection.run_sync(_insert_service)
    actor_id = await async_connection.run_sync(_insert_user)
    active_id = await async_connection.run_sync(
        lambda c: _insert_scoring_config(c, service_id, status="ACTIVE", version=1)
    )

    with pytest.raises(NotADraft):
        await activate_scoring_config(
            async_session,
            config_id=active_id,
            actor_id=actor_id,
            change_note="should fail",
            now=datetime.now(tz=UTC),
        )
