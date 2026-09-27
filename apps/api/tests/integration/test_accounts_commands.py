"""Integration tests of [`accounts.commands`](/architecture/services/api.md#design)
(`S-ACC-01` to `S-ACC-03`, `API-21`, `API-22`, `API-24`) against a real database ([Account
identity](/architecture/rules.md#account-identity), [Account attributes]
(/architecture/rules.md#account-attributes), [Rescoring](/architecture/rules.md#rescoring)
Triggers)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.commands import (
    AccountCreateData,
    AccountUpdateData,
    create_account,
    import_accounts,
    update_account,
)
from leadradar.accounts.errors import (
    AccountNotFound,
    DomainConflict,
    ImportTooLarge,
    InvalidAccountDomain,
    UnknownIndustry,
    UnknownParentAccount,
)
from leadradar.accounts.queries import NewSourceInput, SourceUpdateInput
from leadradar.core.account_import import ImportRowOutcome
from leadradar.core.enums import (
    AccountOrigin,
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AccountStatus,
    AppUserRole,
    AppUserStatus,
    IndustryStatus,
    PipelineRunKind,
    PipelineRunTrigger,
    ServiceStatus,
)
from leadradar.db.models.accounts import Account, AccountAlias, AccountSource
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.configuration import Industry, Service
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import PipelineRun

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 15, tzinfo=UTC)


async def _make_actor(session: AsyncSession) -> uuid.UUID:
    user = AppUser(
        email=f"user-{uuid.uuid4()}@example.com",
        display_name="Test User",
        role=AppUserRole.SALES,
        status=AppUserStatus.ACTIVE,
        password_hash="hash",
        failed_logins=0,
        locked_until=None,
        last_login_at=None,
    )
    session.add(user)
    await session.flush()
    return user.id


async def _make_industry(
    session: AsyncSession, *, status: IndustryStatus = IndustryStatus.ACTIVE
) -> str:
    code = f"IND_{uuid.uuid4().hex[:8].upper()}"
    session.add(Industry(code=code, label=f"Label {code}", status=status))
    await session.flush()
    return code


async def _make_service(
    session: AsyncSession, *, status: ServiceStatus = ServiceStatus.ACTIVE
) -> uuid.UUID:
    unique = uuid.uuid4().hex[:8].upper()
    service = Service(
        code=f"SERVICE_{unique}",
        name=f"Service {unique}",
        description="A service.",
        value_proposition="A value proposition.",
        status=status,
    )
    session.add(service)
    await session.flush()
    return service.id


async def _make_account(session: AsyncSession, **overrides: object) -> Account:
    defaults: dict[str, object] = {
        "domain": f"{uuid.uuid4().hex[:12]}.example.com",
        "name": "Example Corp",
        "country_code": None,
        "industry": None,
        "employee_count": None,
        "revenue_eur": None,
        "operational_complexity": None,
        "attribute_origin": {},
        "parent_account_id": None,
        "origin": AccountOrigin.MANUAL,
        "status": AccountStatus.ACTIVE,
        "crunchbase_id": None,
        "linkedin_url": None,
        "notes": None,
        "last_refreshed_at": None,
        "next_refresh_at": None,
    }
    defaults.update(overrides)
    account = Account(**defaults)
    session.add(account)
    await session.flush()
    return account


async def _count(session: AsyncSession, model: type) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


# --- create_account -----------------------------------------------------------------------


async def test_create_account_normalises_the_domain_and_writes_the_website_source_and_name_alias(
    db_session: AsyncSession,
) -> None:
    actor_id = await _make_actor(db_session)
    result = await create_account(
        db_session,
        data=AccountCreateData(domain="https://www.Lufthansa.com/de", name="Deutsche Lufthansa AG"),
        actor_id=actor_id,
        now=NOW,
    )

    assert result.row.domain == "lufthansa.com"
    assert result.row.origin == AccountOrigin.MANUAL
    assert result.row.status == AccountStatus.ACTIVE
    assert result.aliases == ("Deutsche Lufthansa AG",)
    assert len(result.sources) == 1
    assert result.sources[0].url == "https://lufthansa.com/"
    assert result.sources[0].kind == AccountSourceKind.WEBSITE

    audit_rows = (
        (await db_session.execute(select(AuditEvent).where(AuditEvent.action == "ACCOUNT_CREATED")))
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].payload == {"domain": "lufthansa.com", "origin": "MANUAL"}
    assert audit_rows[0].actor_id == actor_id
    assert audit_rows[0].entity_id == result.row.id


async def test_create_account_writes_manual_attribute_origin_for_given_fields(
    db_session: AsyncSession,
) -> None:
    result = await create_account(
        db_session,
        data=AccountCreateData(
            domain="dhl.com",
            name="DHL Group",
            country_code="DE",
            employee_count=594000,
        ),
        actor_id=await _make_actor(db_session),
        now=NOW,
    )

    assert result.attribute_origin == {"country_code": "MANUAL", "employee_count": "MANUAL"}
    assert "industry" not in result.attribute_origin


async def test_create_account_with_an_existing_domain_raises_domain_conflict_naming_it(
    db_session: AsyncSession,
) -> None:
    existing = await _make_account(db_session, domain="dhl.com")

    with pytest.raises(DomainConflict) as excinfo:
        await create_account(
            db_session,
            data=AccountCreateData(domain="https://group.dhl.com/", name="DHL Group"),
            actor_id=await _make_actor(db_session),
            now=NOW,
        )

    assert excinfo.value.existing_account_id == existing.id
    assert await _count(db_session, Account) == 1


async def test_create_account_with_an_unparseable_domain_raises_invalid_account_domain(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(InvalidAccountDomain):
        await create_account(
            db_session,
            data=AccountCreateData(domain="not a domain", name="X"),
            actor_id=await _make_actor(db_session),
            now=NOW,
        )


async def test_create_account_with_an_inactive_industry_raises_unknown_industry(
    db_session: AsyncSession,
) -> None:
    code = await _make_industry(db_session, status=IndustryStatus.INACTIVE)

    with pytest.raises(UnknownIndustry):
        await create_account(
            db_session,
            data=AccountCreateData(domain="dhl.com", name="DHL", industry=code),
            actor_id=await _make_actor(db_session),
            now=NOW,
        )


async def test_create_account_with_an_unknown_parent_raises_unknown_parent_account(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(UnknownParentAccount):
        await create_account(
            db_session,
            data=AccountCreateData(domain="dhl.com", name="DHL", parent_account_id=uuid.uuid4()),
            actor_id=await _make_actor(db_session),
            now=NOW,
        )


async def test_create_account_inserts_given_aliases_and_sources(db_session: AsyncSession) -> None:
    result = await create_account(
        db_session,
        data=AccountCreateData(
            domain="dhl.com",
            name="DHL Group",
            aliases=("Deutsche Post DHL",),
            sources=(NewSourceInput(kind=AccountSourceKind.NEWSROOM, url="https://dhl.com/news"),),
        ),
        actor_id=await _make_actor(db_session),
        now=NOW,
    )

    assert set(result.aliases) == {"DHL Group", "Deutsche Post DHL"}
    kinds = {s.kind for s in result.sources}
    assert kinds == {AccountSourceKind.WEBSITE, AccountSourceKind.NEWSROOM}


# --- update_account -------------------------------------------------------------------------


async def test_update_account_writes_manual_origin_and_enqueues_a_rescore_per_active_service(
    db_session: AsyncSession,
) -> None:
    account = await _make_account(db_session, employee_count=1000, attribute_origin={})
    active_service_1 = await _make_service(db_session)
    active_service_2 = await _make_service(db_session)
    await _make_service(db_session, status=ServiceStatus.INACTIVE)
    actor_id = await _make_actor(db_session)

    result = await update_account(
        db_session,
        account_id=account.id,
        data=AccountUpdateData(employee_count=2000),
        actor_id=actor_id,
        now=NOW,
    )

    assert result.employee_count == 2000
    assert result.attribute_origin["employee_count"] == "MANUAL"

    audit_rows = (
        (await db_session.execute(select(AuditEvent).where(AuditEvent.action == "ACCOUNT_UPDATED")))
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].payload == {"employee_count": 2000}
    assert audit_rows[0].actor_id == actor_id

    runs = (
        (
            await db_session.execute(
                select(PipelineRun).where(
                    PipelineRun.account_id == account.id,
                    PipelineRun.kind == PipelineRunKind.RESCORE,
                )
            )
        )
        .scalars()
        .all()
    )
    assert {r.service_id for r in runs} == {active_service_1, active_service_2}
    assert all(r.trigger == PipelineRunTrigger.ACCOUNT_CHANGE for r in runs)


async def test_update_account_with_no_change_writes_no_audit_row_and_no_rescore(
    db_session: AsyncSession,
) -> None:
    account = await _make_account(db_session, employee_count=1000)
    await _make_service(db_session)

    await update_account(
        db_session,
        account_id=account.id,
        data=AccountUpdateData(employee_count=1000),
        actor_id=await _make_actor(db_session),
        now=NOW,
    )

    assert await _count(db_session, AuditEvent) == 0
    assert await _count(db_session, PipelineRun) == 0


async def test_update_account_on_an_unknown_id_raises_account_not_found(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(AccountNotFound):
        await update_account(
            db_session,
            account_id=uuid.uuid4(),
            data=AccountUpdateData(employee_count=1),
            actor_id=await _make_actor(db_session),
            now=NOW,
        )


async def test_update_account_replaces_aliases_keeping_the_name_alias(
    db_session: AsyncSession,
) -> None:
    account = await _make_account(db_session, name="DHL Group")
    db_session.add(AccountAlias(account_id=account.id, alias="DHL Group", normalised="dhl"))
    db_session.add(AccountAlias(account_id=account.id, alias="Old Alias", normalised="old alias"))
    await db_session.flush()

    result = await update_account(
        db_session,
        account_id=account.id,
        data=AccountUpdateData(aliases=("Deutsche Post DHL",)),
        actor_id=await _make_actor(db_session),
        now=NOW,
    )

    assert set(result.aliases) == {"DHL Group", "Deutsche Post DHL"}


async def test_update_account_replaces_sources_toggling_a_detected_status_and_dropping_a_manual(
    db_session: AsyncSession,
) -> None:
    account = await _make_account(db_session)
    db_session.add(
        AccountSource(
            account_id=account.id,
            kind=AccountSourceKind.NEWSROOM,
            url="https://example.com/news",
            origin=AccountSourceOrigin.DETECTED,
            status=AccountSourceStatus.ACTIVE,
        )
    )
    db_session.add(
        AccountSource(
            account_id=account.id,
            kind=AccountSourceKind.CAREERS,
            url="https://example.com/careers",
            origin=AccountSourceOrigin.MANUAL,
            status=AccountSourceStatus.ACTIVE,
        )
    )
    await db_session.flush()

    result = await update_account(
        db_session,
        account_id=account.id,
        data=AccountUpdateData(
            sources=(
                SourceUpdateInput(
                    kind=AccountSourceKind.NEWSROOM,
                    url="https://example.com/news",
                    status=AccountSourceStatus.INACTIVE,
                ),
            )
        ),
        actor_id=await _make_actor(db_session),
        now=NOW,
    )

    sources_by_url = {s.url: s for s in result.sources}
    assert sources_by_url["https://example.com/news"].status == AccountSourceStatus.INACTIVE
    assert sources_by_url["https://example.com/news"].origin == AccountSourceOrigin.DETECTED
    assert "https://example.com/careers" not in sources_by_url


# --- import_accounts ------------------------------------------------------------------------


def _csv(*rows: str) -> str:
    header = "domain,name,country_code,industry,employee_count,revenue_eur,aliases"
    return "\n".join([header, *rows]) + "\n"


async def test_import_accounts_dry_run_writes_nothing(db_session: AsyncSession) -> None:
    result = await import_accounts(
        db_session,
        file_text=_csv("dhl.com,DHL Group,DE,,,,"),
        dry_run=True,
        import_max_rows=2000,
        actor_id=await _make_actor(db_session),
        now=NOW,
    )

    assert result.dry_run is True
    assert result.created == 1
    assert result.rows[0].outcome == ImportRowOutcome.CREATED
    assert result.rows[0].account_id is None
    assert await _count(db_session, Account) == 0
    assert await _count(db_session, AuditEvent) == 0


async def test_import_accounts_creates_updates_and_flags_a_possible_duplicate(
    db_session: AsyncSession,
) -> None:
    existing = await _make_account(db_session, domain="lufthansagroup.com", employee_count=None)
    db_session.add(AccountAlias(account_id=existing.id, alias="Example Corp", normalised="example"))
    duplicate_target = await _make_account(db_session, domain="dhl-group.example.com")
    db_session.add(
        AccountAlias(account_id=duplicate_target.id, alias="DHL Group", normalised="dhl")
    )
    await db_session.flush()

    text = _csv(
        "lufthansagroup.com,Lufthansa Group,DE,,140000,,",
        "dhl.com,DHL Group,DE,,,,",
        "swiss.com,SWISS,CH,,,,",
    )

    result = await import_accounts(
        db_session,
        file_text=text,
        dry_run=False,
        import_max_rows=2000,
        actor_id=await _make_actor(db_session),
        now=NOW,
    )

    assert result.created == 1
    assert result.updated == 1
    assert result.duplicates == 1
    assert result.invalid == 0

    outcomes = {row.domain: row.outcome for row in result.rows}
    assert outcomes["lufthansagroup.com"] == ImportRowOutcome.UPDATED
    assert outcomes["dhl.com"] == ImportRowOutcome.POSSIBLE_DUPLICATE
    assert outcomes["swiss.com"] == ImportRowOutcome.CREATED

    await db_session.refresh(existing)
    assert existing.employee_count == 140000
    assert existing.attribute_origin["employee_count"] == "MANUAL"

    imported_audit = (
        (
            await db_session.execute(
                select(AuditEvent).where(AuditEvent.action == "ACCOUNTS_IMPORTED")
            )
        )
        .scalars()
        .all()
    )
    assert len(imported_audit) == 1
    assert imported_audit[0].payload == {
        "rows": 3,
        "created": 1,
        "updated": 1,
        "duplicates": 1,
        "invalid": 0,
    }

    created_rows = (
        (await db_session.execute(select(AuditEvent).where(AuditEvent.action == "ACCOUNT_CREATED")))
        .scalars()
        .all()
    )
    assert len(created_rows) == 1
    updated_rows = (
        (await db_session.execute(select(AuditEvent).where(AuditEvent.action == "ACCOUNT_UPDATED")))
        .scalars()
        .all()
    )
    assert len(updated_rows) == 1


async def test_import_accounts_reports_an_invalid_row_without_writing_it(
    db_session: AsyncSession,
) -> None:
    result = await import_accounts(
        db_session,
        file_text=_csv(",Missing Domain,,,,,"),
        dry_run=False,
        import_max_rows=2000,
        actor_id=await _make_actor(db_session),
        now=NOW,
    )

    assert result.invalid == 1
    assert result.rows[0].outcome == ImportRowOutcome.INVALID
    assert result.rows[0].errors == (("domain", "domain is required."),)
    assert await _count(db_session, Account) == 0


async def test_import_accounts_over_the_row_limit_raises_import_too_large_and_writes_nothing(
    db_session: AsyncSession,
) -> None:
    text = _csv(*(f"account-{i}.example.com,Account {i},,,,," for i in range(3)))

    with pytest.raises(ImportTooLarge):
        await import_accounts(
            db_session,
            file_text=text,
            dry_run=False,
            import_max_rows=2,
            actor_id=await _make_actor(db_session),
            now=NOW,
        )

    assert await _count(db_session, Account) == 0


async def test_import_accounts_enqueues_a_rescore_only_when_an_existing_account_changes(
    db_session: AsyncSession,
) -> None:
    existing = await _make_account(db_session, domain="dhl.com", employee_count=1000)
    await _make_service(db_session)

    result = await import_accounts(
        db_session,
        file_text=_csv("dhl.com,DHL Group,,,1000,,"),  # same employee_count: no real change
        dry_run=False,
        import_max_rows=2000,
        actor_id=await _make_actor(db_session),
        now=NOW,
    )

    assert result.updated == 1
    assert await _count(db_session, PipelineRun) == 0
    assert (
        await db_session.execute(select(AuditEvent).where(AuditEvent.action == "ACCOUNT_UPDATED"))
    ).first() is None
    assert existing.employee_count == 1000
