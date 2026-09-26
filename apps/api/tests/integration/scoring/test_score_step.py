"""Integration tests for the SCORE step, the job queue and the activation transaction.

Uses a real PostgreSQL container (via testcontainers) and direct SQL through the
`sync_connection` fixture.  No mocks; assertions are on the database state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, text

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_service(conn: Connection) -> uuid.UUID:
    service_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO service (id, code, name, description, value_proposition, status, created_at, updated_at) "
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
        "default_half_life_days": {"NEWS": 90, "COMPANY_PUBLICATION": 365, "JOB_POSTING": 60, "COMPANY_PROFILE": 365},
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
            "VALUES (:id, :service_id, :version, :status, :settings::jsonb, NULL, NULL, NULL, now(), now())"
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
            "status, stage, progress, errors, requested_by, started_at, finished_at, created_at, updated_at) "
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

class TestActivationTransaction:
    def test_activation_sets_draft_to_active_and_retires_previous(
        self, sync_connection: Connection
    ) -> None:
        """Activation: draft→ACTIVE, previous ACTIVE→RETIRED, one run+job, 2 audit rows."""
        service_id = _insert_service(sync_connection)
        actor_id = _insert_user(sync_connection)

        # Previous ACTIVE config
        prev_config_id = _insert_scoring_config(sync_connection, service_id, status="ACTIVE", version=1)
        # New DRAFT config
        draft_config_id = _insert_scoring_config(sync_connection, service_id, status="DRAFT", version=2)

        sync_connection.commit()

        # Run activation inside a subtransaction
        import asyncio

        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from leadradar.scoring.activate import activate_scoring_config

        # Use the sync connection's URL to build an async engine
        url = str(sync_connection.engine.url).replace("postgresql+psycopg://", "postgresql://")
        async_url = url.replace("postgresql://", "postgresql+psycopg://")

        async def _run() -> None:
            engine = create_async_engine(async_url)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session, session.begin():
                await activate_scoring_config(
                    session,
                    config_id=draft_config_id,
                    actor_id=actor_id,
                    change_note="v2 go live",
                    request_id="req-1",
                )
            await engine.dispose()

        asyncio.run(_run())

        # Verify DRAFT→ACTIVE
        row = sync_connection.execute(
            text("SELECT status FROM scoring_config WHERE id = :id"), {"id": draft_config_id}
        ).fetchone()
        assert row is not None
        assert row[0] == "ACTIVE"

        # Verify previous ACTIVE→RETIRED
        row = sync_connection.execute(
            text("SELECT status FROM scoring_config WHERE id = :id"), {"id": prev_config_id}
        ).fetchone()
        assert row is not None
        assert row[0] == "RETIRED"

        # Verify one pipeline_run and one job
        run_count = sync_connection.execute(
            text("SELECT COUNT(*) FROM pipeline_run WHERE service_id = :sid AND kind = 'RESCORE'"),
            {"sid": service_id},
        ).scalar()
        assert run_count == 1

        job_count = sync_connection.execute(
            text(
                "SELECT COUNT(*) FROM job j "
                "JOIN pipeline_run pr ON j.run_id = pr.id "
                "WHERE pr.service_id = :sid AND j.step = 'SCORE'"
            ),
            {"sid": service_id},
        ).scalar()
        assert job_count == 1

        # Verify 2 audit rows (SCORING_ACTIVATED + RUN_REQUESTED)
        audit_count = sync_connection.execute(
            text(
                "SELECT COUNT(*) FROM audit_event "
                "WHERE action IN ('SCORING_ACTIVATED', 'RUN_REQUESTED')"
            )
        ).scalar()
        assert audit_count >= 2

    def test_activation_of_non_draft_raises(self, sync_connection: Connection) -> None:
        """Activating an ACTIVE config raises NotADraft."""
        import asyncio

        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from leadradar.scoring.activate import activate_scoring_config
        from leadradar.scoring.errors import NotADraft

        service_id = _insert_service(sync_connection)
        actor_id = _insert_user(sync_connection)
        active_id = _insert_scoring_config(sync_connection, service_id, status="ACTIVE", version=1)
        sync_connection.commit()

        url = str(sync_connection.engine.url).replace("postgresql+psycopg://", "postgresql://")
        async_url = url.replace("postgresql://", "postgresql+psycopg://")

        async def _run() -> None:
            engine = create_async_engine(async_url)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session, session.begin():
                await activate_scoring_config(
                    session,
                    config_id=active_id,
                    actor_id=actor_id,
                    change_note="should fail",
                    request_id=None,
                )
            await engine.dispose()

        with pytest.raises(NotADraft):
            asyncio.run(_run())


class TestJobQueue:
    def test_claiming_sets_job_to_running(self, sync_connection: Connection) -> None:
        """Claiming a READY job sets status=RUNNING, locked_by, locked_at, attempts=1."""
        import asyncio

        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from leadradar.worker.queue import _claim_job

        service_id = _insert_service(sync_connection)
        actor_id = _insert_user(sync_connection)
        run_id = _insert_pipeline_run(sync_connection, service_id, actor_id)
        job_id = _insert_job(sync_connection, run_id)
        sync_connection.commit()

        url = str(sync_connection.engine.url).replace("postgresql+psycopg://", "postgresql://")
        async_url = url.replace("postgresql://", "postgresql+psycopg://")

        async def _run() -> None:
            engine = create_async_engine(async_url)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime.now(tz=UTC)
            async with factory() as session:
                job = await _claim_job(session, "worker-test", now)
                assert job is not None
            await engine.dispose()

        asyncio.run(_run())

        row = sync_connection.execute(
            text("SELECT status, locked_by, attempts FROM job WHERE id = :id"), {"id": job_id}
        ).fetchone()
        assert row is not None
        assert row[0] == "RUNNING"
        assert row[1] == "worker-test"
        assert row[2] == 1

    def test_failed_job_after_max_attempts_sets_failed(self, sync_connection: Connection) -> None:
        """A job that has reached max_attempts is set to FAILED."""
        import asyncio

        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from leadradar.worker.queue import _mark_failed_or_retry

        service_id = _insert_service(sync_connection)
        actor_id = _insert_user(sync_connection)
        run_id = _insert_pipeline_run(sync_connection, service_id, actor_id)
        job_id = _insert_job(sync_connection, run_id, status="RUNNING", attempts=3)
        sync_connection.commit()

        url = str(sync_connection.engine.url).replace("postgresql+psycopg://", "postgresql://")
        async_url = url.replace("postgresql://", "postgresql+psycopg://")

        async def _run() -> None:
            engine = create_async_engine(async_url)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime.now(tz=UTC)
            async with factory() as session:
                await _mark_failed_or_retry(
                    session, job_id, "step error", attempts=3,
                    max_attempts=3, backoff_s=30, now=now,
                )
            await engine.dispose()

        asyncio.run(_run())

        row = sync_connection.execute(
            text("SELECT status, last_error FROM job WHERE id = :id"), {"id": job_id}
        ).fetchone()
        assert row is not None
        assert row[0] == "FAILED"
        assert row[1] == "step error"

    def test_stale_running_job_is_reclaimed(self, sync_connection: Connection) -> None:
        """A RUNNING job past JOB_LOCK_TIMEOUT_S is returned to READY."""
        import asyncio

        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from leadradar.worker.queue import _reclaim_stale_jobs

        service_id = _insert_service(sync_connection)
        actor_id = _insert_user(sync_connection)
        run_id = _insert_pipeline_run(sync_connection, service_id, actor_id)
        job_id = _insert_job(sync_connection, run_id, status="RUNNING")

        # Set locked_at far in the past
        old_locked_at = datetime.now(tz=UTC) - timedelta(seconds=1000)
        sync_connection.execute(
            text("UPDATE job SET locked_at = :ts, locked_by = 'dead-worker' WHERE id = :id"),
            {"ts": old_locked_at, "id": job_id},
        )
        sync_connection.commit()

        url = str(sync_connection.engine.url).replace("postgresql+psycopg://", "postgresql://")
        async_url = url.replace("postgresql://", "postgresql+psycopg://")

        async def _run() -> None:
            engine = create_async_engine(async_url)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            now = datetime.now(tz=UTC)
            async with factory() as session:
                await _reclaim_stale_jobs(session, "worker-new", now, lock_timeout_s=900)
            await engine.dispose()

        asyncio.run(_run())

        row = sync_connection.execute(
            text("SELECT status, locked_by FROM job WHERE id = :id"), {"id": job_id}
        ).fetchone()
        assert row is not None
        assert row[0] == "READY"
        assert row[1] is None
