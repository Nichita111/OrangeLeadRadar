"""Integration tests of `outreach.commands.push_to_crm` (`API-59`, `S-OUT-02`) against a real
database. `outreach.hubspot.upsert_company` is monkeypatched here: no test in this file calls the
real HubSpot service; `test_hubspot.py` unit-tests `upsert_company` itself over an
`httpx.MockTransport`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from leadradar.auth.sessions import Principal
from leadradar.core.enums import (
    AppUserRole,
    CrmSyncStatus,
    CrmSyncTarget,
    FindingStrength,
    ScoringConfigStatus,
    SignalQuestionPolarity,
)
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.outreach import CrmSync
from leadradar.outreach.commands import push_to_crm
from leadradar.outreach.company_push import CompanyPush
from leadradar.outreach.errors import CrmUnavailable, HubspotNotConfigured, ScoreNotFound
from leadradar.settings import ApiSettings
from tests.integration import factories as f

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 15, tzinfo=UTC)


def _settings(*, token_set: bool = True) -> ApiSettings:
    return ApiSettings(
        database_url=SecretStr("postgresql://u:p@localhost/db"),
        hubspot_access_token=SecretStr("a-token") if token_set else None,
        hubspot_top_signals=3,
        app_base_url="http://localhost:8080",
    )


def _principal(user_id: uuid.UUID) -> Principal:
    return Principal(user_id=user_id, display_name="Ada Lovelace", role=AppUserRole.SALES)


async def _count(connection: AsyncConnection, model: type) -> int:
    result = await connection.execute(select(func.count()).select_from(model))
    return result.scalar_one()


async def _make_scored_account(
    connection: AsyncConnection, *, breakdown: dict[str, object] | None = None
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    def _insert(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        account_id = f.make_account(conn, domain="pushable.example.com", name="Pushable GmbH")
        service_id = f.make_service(conn, name="Intelligent Automation")
        scoring_config_id = f.make_scoring_config(
            conn, service_id, status=ScoringConfigStatus.ACTIVE
        )
        run_id = f.make_pipeline_run(conn)
        score_id = f.make_account_score(
            conn,
            account_id,
            service_id,
            scoring_config_id,
            run_id,
            is_current=True,
            breakdown=breakdown or {},
        )
        return account_id, service_id, score_id

    return await connection.run_sync(_insert)


async def _make_user(connection: AsyncConnection) -> uuid.UUID:
    return await connection.run_sync(lambda conn: f.make_app_user(conn))


async def test_a_successful_push_writes_one_succeeded_row_and_one_audit_row(
    async_connection: AsyncConnection,
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account_id, service_id, score_id = await _make_scored_account(async_connection)
    user_id = await _make_user(async_connection)

    async def fake_upsert_company(*args: object, **kwargs: object) -> str:
        return "hubspot-company-1"

    monkeypatch.setattr("leadradar.outreach.commands.upsert_company", fake_upsert_company)

    async with httpx.AsyncClient() as http:
        result = await push_to_crm(
            async_session,
            account_id=account_id,
            service_id=service_id,
            principal=_principal(user_id),
            settings=_settings(),
            http=http,
            now=NOW,
            request_id="req-1",
        )

    assert result.status == CrmSyncStatus.SUCCEEDED
    assert result.external_id == "hubspot-company-1"

    row = (await async_session.execute(select(CrmSync).where(CrmSync.id == result.id))).scalar_one()
    assert row.status == CrmSyncStatus.SUCCEEDED
    assert row.external_id == "hubspot-company-1"
    assert row.target == CrmSyncTarget.HUBSPOT
    assert row.requested_by == user_id
    assert row.score_id == score_id

    audit_rows = (
        (await async_session.execute(select(AuditEvent).where(AuditEvent.entity_id == result.id)))
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "CRM_PUSHED"
    assert audit_rows[0].kind == "CRM"
    assert audit_rows[0].payload == {"target": "HUBSPOT", "status": "SUCCEEDED"}


async def test_an_adapter_failure_commits_a_failed_row_and_reraises(
    async_connection: AsyncConnection,
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account_id, service_id, _score_id = await _make_scored_account(async_connection)
    user_id = await _make_user(async_connection)

    async def fake_upsert_company(*args: object, **kwargs: object) -> str:
        raise CrmUnavailable("HubSpot answered 401.")

    monkeypatch.setattr("leadradar.outreach.commands.upsert_company", fake_upsert_company)

    async with httpx.AsyncClient() as http:
        with pytest.raises(CrmUnavailable):
            await push_to_crm(
                async_session,
                account_id=account_id,
                service_id=service_id,
                principal=_principal(user_id),
                settings=_settings(),
                http=http,
                now=NOW,
                request_id="req-1",
            )

    rows = (
        (await async_session.execute(select(CrmSync).where(CrmSync.account_id == account_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].status == CrmSyncStatus.FAILED
    assert rows[0].error == "HubSpot answered 401."
    assert rows[0].external_id is None

    audit_rows = (
        (await async_session.execute(select(AuditEvent).where(AuditEvent.action == "CRM_PUSHED")))
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].payload == {"target": "HUBSPOT", "status": "FAILED"}


async def test_with_the_token_unset_it_raises_before_any_read_or_write_even_without_a_score(
    async_connection: AsyncConnection,
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = await _make_user(async_connection)

    async def boom(*args: object, **kwargs: object) -> str:
        raise AssertionError("upsert_company must not be called")

    monkeypatch.setattr("leadradar.outreach.commands.upsert_company", boom)

    async with httpx.AsyncClient() as http:
        with pytest.raises(HubspotNotConfigured):
            await push_to_crm(
                async_session,
                account_id=uuid.uuid4(),
                service_id=uuid.uuid4(),
                principal=_principal(user_id),
                settings=_settings(token_set=False),
                http=http,
                now=NOW,
                request_id="req-1",
            )

    assert await _count(async_connection, CrmSync) == 0


async def test_with_a_token_and_no_current_score_it_raises_score_not_found_and_writes_nothing(
    async_connection: AsyncConnection,
    async_session: AsyncSession,
) -> None:
    user_id = await _make_user(async_connection)

    async with httpx.AsyncClient() as http:
        with pytest.raises(ScoreNotFound):
            await push_to_crm(
                async_session,
                account_id=uuid.uuid4(),
                service_id=uuid.uuid4(),
                principal=_principal(user_id),
                settings=_settings(),
                http=http,
                now=NOW,
                request_id="req-1",
            )

    assert await _count(async_connection, CrmSync) == 0


async def test_the_push_reads_the_current_score_row_not_a_superseded_one(
    async_connection: AsyncConnection,
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _insert(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        account_id = f.make_account(conn)
        service_id = f.make_service(conn)
        scoring_config_id = f.make_scoring_config(
            conn, service_id, status=ScoringConfigStatus.ACTIVE
        )
        run_id = f.make_pipeline_run(conn)
        f.make_account_score(
            conn,
            account_id,
            service_id,
            scoring_config_id,
            run_id,
            is_current=False,
            priority=10,
        )
        f.make_account_score(
            conn,
            account_id,
            service_id,
            scoring_config_id,
            run_id,
            is_current=True,
            priority=90,
        )
        return account_id, service_id

    account_id, service_id = await async_connection.run_sync(_insert)
    user_id = await _make_user(async_connection)

    seen_priority: list[str] = []

    async def fake_upsert_company(
        http: object, token: str, push: CompanyPush, timeout_s: float
    ) -> str:
        seen_priority.append(push.leadradar_priority)
        return "hubspot-1"

    monkeypatch.setattr("leadradar.outreach.commands.upsert_company", fake_upsert_company)

    async with httpx.AsyncClient() as http:
        await push_to_crm(
            async_session,
            account_id=account_id,
            service_id=service_id,
            principal=_principal(user_id),
            settings=_settings(),
            http=http,
            now=NOW,
            request_id="req-1",
        )

    assert seen_priority == ["90"]


async def test_two_pushes_record_two_attempts_each_with_its_own_row(
    async_connection: AsyncConnection,
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account_id, service_id, _score_id = await _make_scored_account(async_connection)
    user_id = await _make_user(async_connection)

    async def fake_upsert_company(*args: object, **kwargs: object) -> str:
        return "hubspot-1"

    monkeypatch.setattr("leadradar.outreach.commands.upsert_company", fake_upsert_company)

    async with httpx.AsyncClient() as http:
        for request_id in ("req-1", "req-2"):
            await push_to_crm(
                async_session,
                account_id=account_id,
                service_id=service_id,
                principal=_principal(user_id),
                settings=_settings(),
                http=http,
                now=NOW,
                request_id=request_id,
            )

    rows = (
        (await async_session.execute(select(CrmSync).where(CrmSync.account_id == account_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert rows[0].id != rows[1].id


async def test_top_signals_are_the_positive_findings_with_the_most_points(
    async_connection: AsyncConnection,
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _insert(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        service_id = f.make_service(conn)
        question_id = f.make_signal_question(
            conn, service_id, text="Does it hire?", polarity=SignalQuestionPolarity.POSITIVE
        )
        account_id = f.make_account(conn)
        run_id = f.make_pipeline_run(conn)
        document_id = f.make_document(conn, run_id)
        chunk_id = f.make_chunk(conn, document_id)
        classification_id = f.make_classification(conn, chunk_id, question_id, run_id)
        finding_id = f.make_finding(
            conn,
            account_id,
            question_id,
            classification_id,
            chunk_id,
            quote="We are hiring.",
            strength=FindingStrength.STRONG,
            observed_at=NOW,
        )
        scoring_config_id = f.make_scoring_config(
            conn, service_id, status=ScoringConfigStatus.ACTIVE
        )
        f.make_account_score(
            conn,
            account_id,
            service_id,
            scoring_config_id,
            run_id,
            is_current=True,
            breakdown={
                "intent": {
                    "questions": [
                        {
                            "question_key": "HIRING",
                            "polarity": "POSITIVE",
                            "finding_id": str(finding_id),
                            "points": 42.0,
                        }
                    ]
                }
            },
        )
        return account_id, service_id, finding_id

    account_id, service_id, _finding_id = await async_connection.run_sync(_insert)
    user_id = await _make_user(async_connection)

    seen_signals: list[str] = []

    async def fake_upsert_company(
        http: object, token: str, push: CompanyPush, timeout_s: float
    ) -> str:
        seen_signals.append(push.leadradar_top_signals)
        return "hubspot-1"

    monkeypatch.setattr("leadradar.outreach.commands.upsert_company", fake_upsert_company)

    async with httpx.AsyncClient() as http:
        await push_to_crm(
            async_session,
            account_id=account_id,
            service_id=service_id,
            principal=_principal(user_id),
            settings=_settings(),
            http=http,
            now=NOW,
            request_id="req-1",
        )

    assert seen_signals == ['Does it hire? — "We are hiring."']
