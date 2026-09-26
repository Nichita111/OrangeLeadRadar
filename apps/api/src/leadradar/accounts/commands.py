"""[Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts), the accounts half
(`API-21`, `API-22`, `API-24`, `S-ACC-01` to `S-ACC-03`): creates and updates
[`account`](/architecture/sql-store.md#account) rows, their aliases and sources, imports a CSV,
and enqueues the [Rescoring](/architecture/rules.md#rescoring) an attribute change requires. Each
function owns its own transaction, as [`auth.users`](../auth/users.py) does."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.errors import (
    AccountNotFound,
    DomainConflict,
    ImportTooLarge,
    InvalidAccountDomain,
    UnknownIndustry,
    UnknownParentAccount,
)
from leadradar.accounts.queries import (
    AccountData,
    NewSourceInput,
    SourceUpdateInput,
    account_data,
)
from leadradar.audit.events import append_audit_event
from leadradar.core.account_identity import InvalidDomain, normalise_domain, normalise_name
from leadradar.core.account_import import (
    ImportRowOutcome,
    ParsedImportRow,
    parse_csv_rows,
    parse_import_row,
)
from leadradar.core.enums import (
    AccountOperationalComplexity,
    AccountOrigin,
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AccountStatus,
    AuditAction,
    IndustryStatus,
    PipelineRunTrigger,
    ServiceStatus,
)
from leadradar.core.sign_in import changed_fields
from leadradar.db.models.accounts import Account, AccountAlias, AccountSource
from leadradar.db.models.configuration import Industry, Service
from leadradar.runs.enqueue import enqueue_account_rescore

#: The five [Account attributes](/architecture/rules.md#account-attributes) columns whose origin
#: is tracked in `account.attribute_origin`.
_ATTRIBUTE_FIELDS = (
    "country_code",
    "industry",
    "employee_count",
    "revenue_eur",
    "operational_complexity",
)

#: `AccountUpdate`'s other plain fields ([Accounts and contacts]
#: (/architecture/interfaces.md#accountcreate)): edited the same way, but without an origin.
_PLAIN_FIELDS = ("parent_account_id", "linkedin_url", "notes", "status")


@dataclass(frozen=True)
class AccountCreateData:
    """[`AccountCreate`](/architecture/interfaces.md#accountcreate), the request of `API-21`."""

    domain: str
    name: str
    country_code: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue_eur: int | None = None
    operational_complexity: AccountOperationalComplexity | None = None
    parent_account_id: uuid.UUID | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    aliases: tuple[str, ...] = ()
    sources: tuple[NewSourceInput, ...] = ()


@dataclass(frozen=True)
class AccountUpdateData:
    """[`AccountUpdate`](/architecture/interfaces.md#accountupdate), the request of `API-24`. A
    field left `None` was not sent, the same convention
    [`UserUpdateData`](../auth/users.py) documents: none of these fields can be explicitly
    cleared to null through this endpoint, only replaced by a new value."""

    country_code: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue_eur: int | None = None
    operational_complexity: AccountOperationalComplexity | None = None
    parent_account_id: uuid.UUID | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    status: AccountStatus | None = None
    aliases: tuple[str, ...] | None = None
    sources: tuple[SourceUpdateInput, ...] | None = None

    def sent_scalar_fields(self) -> dict[str, object]:
        values: dict[str, object] = {
            "country_code": self.country_code,
            "industry": self.industry,
            "employee_count": self.employee_count,
            "revenue_eur": self.revenue_eur,
            "operational_complexity": self.operational_complexity,
            "parent_account_id": self.parent_account_id,
            "linkedin_url": self.linkedin_url,
            "notes": self.notes,
            "status": self.status,
        }
        return {field_name: value for field_name, value in values.items() if value is not None}


@dataclass(frozen=True)
class ImportRowResult:
    """One entry of `ImportResult.rows` ([Accounts and contacts]
    (/architecture/interfaces.md#importresult))."""

    line: int
    domain: str | None
    outcome: ImportRowOutcome
    account_id: uuid.UUID | None
    errors: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ImportResultData:
    """[`ImportResult`](/architecture/interfaces.md#importresult), the response of `API-22`."""

    dry_run: bool
    rows: tuple[ImportRowResult, ...] = field(default_factory=tuple)
    created: int = 0
    updated: int = 0
    duplicates: int = 0
    invalid: int = 0


def _dump_value(value: object) -> object:
    """JSON-safe form of one attribute value for an audit payload or `attribute_origin`: an
    enum's own store value, a UUID's string form, anything else unchanged."""
    if hasattr(value, "value") and not isinstance(value, str):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


async def _find_account_by_domain(session: AsyncSession, domain: str) -> Account | None:
    return (
        await session.execute(select(Account).where(Account.domain == domain))
    ).scalar_one_or_none()


async def _find_account_by_name_match(session: AsyncSession, name: str) -> Account | None:
    """[Account identity](/architecture/rules.md#account-identity) Matching: a company matches
    an account when its normalised name equals one of the account's normalised aliases."""
    normalised = normalise_name(name)
    return (
        (
            await session.execute(
                select(Account)
                .join(AccountAlias, AccountAlias.account_id == Account.id)
                .where(AccountAlias.normalised == normalised)
                .limit(1)
            )
        )
        .scalars()
        .first()
    )


async def _ensure_active_industry(session: AsyncSession, code: str) -> None:
    exists = (
        await session.execute(
            select(Industry.code).where(
                Industry.code == code, Industry.status == IndustryStatus.ACTIVE
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise UnknownIndustry("industry", f"'{code}' is not an active industry.")


async def _ensure_account_exists(session: AsyncSession, account_id: uuid.UUID) -> None:
    exists = (
        await session.execute(select(Account.id).where(Account.id == account_id))
    ).scalar_one_or_none()
    if exists is None:
        raise UnknownParentAccount("parent_account_id", f"No account {account_id}.")


async def _active_service_ids(session: AsyncSession) -> list[uuid.UUID]:
    return list(
        (await session.execute(select(Service.id).where(Service.status == ServiceStatus.ACTIVE)))
        .scalars()
        .all()
    )


async def _write_alias(session: AsyncSession, account_id: uuid.UUID, alias: str) -> None:
    normalised = normalise_name(alias)
    if not normalised:
        return
    stmt = (
        pg_insert(AccountAlias)
        .values(account_id=account_id, alias=alias, normalised=normalised)
        .on_conflict_do_nothing(index_elements=["account_id", "normalised"])
    )
    await session.execute(stmt)


async def _write_source(
    session: AsyncSession,
    account_id: uuid.UUID,
    kind: AccountSourceKind,
    url: str,
    *,
    status: AccountSourceStatus = AccountSourceStatus.ACTIVE,
    origin: AccountSourceOrigin = AccountSourceOrigin.MANUAL,
) -> None:
    stmt = (
        pg_insert(AccountSource)
        .values(account_id=account_id, kind=kind, url=url, origin=origin, status=status)
        .on_conflict_do_nothing(index_elements=["account_id", "url"])
    )
    await session.execute(stmt)


async def _insert_new_account(
    session: AsyncSession,
    *,
    domain: str,
    name: str,
    origin: AccountOrigin,
    country_code: str | None,
    industry: str | None,
    employee_count: int | None,
    revenue_eur: int | None,
    operational_complexity: AccountOperationalComplexity | None,
    parent_account_id: uuid.UUID | None = None,
    linkedin_url: str | None = None,
    notes: str | None = None,
    aliases: tuple[str, ...],
    sources: tuple[tuple[AccountSourceKind, str], ...],
) -> Account:
    """Inserts the account row, the name alias, the `WEBSITE` home-page source and every other
    alias and source given, shared by `create_account` (`API-21`) and `import_accounts`
    (`API-22`, a new domain)."""
    attribute_origin = {
        field_name: "MANUAL"
        for field_name, value in (
            ("country_code", country_code),
            ("industry", industry),
            ("employee_count", employee_count),
            ("revenue_eur", revenue_eur),
            ("operational_complexity", operational_complexity),
        )
        if value is not None
    }

    account = Account(
        domain=domain,
        name=name,
        country_code=country_code,
        industry=industry,
        employee_count=employee_count,
        revenue_eur=revenue_eur,
        operational_complexity=operational_complexity,
        attribute_origin=attribute_origin,
        parent_account_id=parent_account_id,
        origin=origin,
        status=AccountStatus.ACTIVE,
        crunchbase_id=None,
        linkedin_url=linkedin_url,
        notes=notes,
        last_refreshed_at=None,
        next_refresh_at=None,
    )
    session.add(account)
    await session.flush()

    await _write_alias(session, account.id, name)
    for alias in aliases:
        await _write_alias(session, account.id, alias)

    website_url = f"https://{domain}/"
    await _write_source(session, account.id, AccountSourceKind.WEBSITE, website_url)
    for kind, url in sources:
        if (kind, url) == (AccountSourceKind.WEBSITE, website_url):
            continue
        await _write_source(session, account.id, kind, url)

    return account


async def create_account(
    session: AsyncSession, *, data: AccountCreateData, actor_id: uuid.UUID, now: datetime
) -> AccountData:
    """`API-21`. Raises `InvalidAccountDomain`, `DomainConflict` (`details.entity_id` names the
    existing account), `UnknownIndustry`, `UnknownParentAccount`."""
    try:
        domain = normalise_domain(data.domain)
    except InvalidDomain as exc:
        raise InvalidAccountDomain("domain", str(exc)) from exc

    existing = await _find_account_by_domain(session, domain)
    if existing is not None:
        raise DomainConflict(existing.id, f"An account for {domain} already exists.")

    if data.industry is not None:
        await _ensure_active_industry(session, data.industry)
    if data.parent_account_id is not None:
        await _ensure_account_exists(session, data.parent_account_id)

    try:
        account = await _insert_new_account(
            session,
            domain=domain,
            name=data.name,
            origin=AccountOrigin.MANUAL,
            country_code=data.country_code,
            industry=data.industry,
            employee_count=data.employee_count,
            revenue_eur=data.revenue_eur,
            operational_complexity=data.operational_complexity,
            parent_account_id=data.parent_account_id,
            linkedin_url=data.linkedin_url,
            notes=data.notes,
            aliases=data.aliases,
            sources=tuple((s.kind, s.url) for s in data.sources),
        )
    except IntegrityError:
        await session.rollback()
        conflicting = await _find_account_by_domain(session, domain)
        assert conflicting is not None
        raise DomainConflict(conflicting.id, f"An account for {domain} already exists.") from None

    await append_audit_event(
        session,
        action=AuditAction.ACCOUNT_CREATED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="account",
        entity_id=account.id,
        payload={"domain": domain, "origin": AccountOrigin.MANUAL.value},
    )
    result = await account_data(session, account)
    await session.commit()
    return result


def _apply_manual_value(account: Account, field_name: str, value: object) -> None:
    """Writes `value` to `field_name`, and, for one of the five tracked attributes, records its
    origin as `MANUAL` ([Account attributes](/architecture/rules.md#account-attributes): "A
    user's edit always writes MANUAL")."""
    setattr(account, field_name, value)
    if field_name in _ATTRIBUTE_FIELDS:
        account.attribute_origin = {**account.attribute_origin, field_name: "MANUAL"}


async def _replace_aliases(
    session: AsyncSession, account: Account, new_aliases: tuple[str, ...]
) -> bool:
    """`API-24`'s note: "`aliases` replaces the aliases (the name alias is kept)"."""
    name_normalised = normalise_name(account.name)
    existing = (
        (await session.execute(select(AccountAlias).where(AccountAlias.account_id == account.id)))
        .scalars()
        .all()
    )
    existing_by_normalised = {row.normalised: row for row in existing}
    keep = {name_normalised}
    changed = False
    for alias in new_aliases:
        normalised = normalise_name(alias)
        if not normalised:
            continue
        keep.add(normalised)
        if normalised not in existing_by_normalised:
            await _write_alias(session, account.id, alias)
            changed = True
    for row in existing:
        if row.normalised not in keep:
            await session.delete(row)
            changed = True
    return changed


async def _replace_sources(
    session: AsyncSession, account: Account, new_sources: tuple[SourceUpdateInput, ...]
) -> bool:
    """`API-24`'s note: "`sources` replaces the `MANUAL` sources and may set a `DETECTED`
    source's status"."""
    existing = (
        (await session.execute(select(AccountSource).where(AccountSource.account_id == account.id)))
        .scalars()
        .all()
    )
    existing_by_url = {row.url: row for row in existing}
    kept_manual_urls: set[str] = set()
    changed = False
    for item in new_sources:
        row = existing_by_url.get(item.url)
        if row is None:
            await _write_source(session, account.id, item.kind, item.url, status=item.status)
            kept_manual_urls.add(item.url)
            changed = True
            continue
        if row.origin == AccountSourceOrigin.DETECTED:
            if row.status != item.status:
                row.status = item.status
                changed = True
            continue
        kept_manual_urls.add(item.url)
        if row.kind != item.kind or row.status != item.status:
            row.kind = item.kind
            row.status = item.status
            changed = True
    for row in existing:
        if row.origin == AccountSourceOrigin.MANUAL and row.url not in kept_manual_urls:
            await session.delete(row)
            changed = True
    return changed


async def _enqueue_account_change_rescores(
    session: AsyncSession, *, account_id: uuid.UUID, actor_id: uuid.UUID, now: datetime
) -> None:
    for service_id in await _active_service_ids(session):
        await enqueue_account_rescore(
            session,
            account_id=account_id,
            service_id=service_id,
            trigger=PipelineRunTrigger.ACCOUNT_CHANGE,
            requested_by=actor_id,
            now=now,
        )


async def update_account(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    data: AccountUpdateData,
    actor_id: uuid.UUID,
    now: datetime,
) -> AccountData:
    """`API-24`. Raises `AccountNotFound`, `UnknownIndustry`, `UnknownParentAccount`. Any
    attribute change enqueues a `RESCORE` with trigger `ACCOUNT_CHANGE` for every active service
    ([Rescoring](/architecture/rules.md#rescoring) Triggers), and writes no audit row when
    nothing changed (matching `auth.users.update_user`'s G8)."""
    account = (
        await session.execute(select(Account).where(Account.id == account_id).with_for_update())
    ).scalar_one_or_none()
    if account is None:
        raise AccountNotFound(f"No account {account_id}.")

    if data.industry is not None:
        await _ensure_active_industry(session, data.industry)
    if data.parent_account_id is not None:
        await _ensure_account_exists(session, data.parent_account_id)

    update = data.sent_scalar_fields()
    current = {
        field_name: getattr(account, field_name)
        for field_name in (*_ATTRIBUTE_FIELDS, *_PLAIN_FIELDS)
    }
    changes = changed_fields(current, update)
    for field_name, value in changes.items():
        _apply_manual_value(account, field_name, value)

    payload = {field_name: _dump_value(value) for field_name, value in changes.items()}

    if data.aliases is not None and await _replace_aliases(session, account, data.aliases):
        payload["aliases"] = list(data.aliases)
    if data.sources is not None and await _replace_sources(session, account, data.sources):
        payload["sources"] = [
            {"kind": s.kind.value, "url": s.url, "status": s.status.value} for s in data.sources
        ]

    if payload:
        await append_audit_event(
            session,
            action=AuditAction.ACCOUNT_UPDATED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type="account",
            entity_id=account.id,
            payload=payload,
        )
        await _enqueue_account_change_rescores(
            session, account_id=account.id, actor_id=actor_id, now=now
        )

    result = await account_data(session, account)
    await session.commit()
    return result


def _apply_import_row_update(account: Account, parsed: ParsedImportRow) -> dict[str, object]:
    """`API-22`'s note: "an existing domain is updated with the columns the row fills, as
    `MANUAL` values". An empty cell (`None`) leaves the column untouched — unlike an explicit
    `AccountUpdate`, a CSV row cannot ask to clear one."""
    update = {
        field_name: value
        for field_name, value in (
            ("country_code", parsed.country_code),
            ("industry", parsed.industry),
            ("employee_count", parsed.employee_count),
            ("revenue_eur", parsed.revenue_eur),
            ("operational_complexity", parsed.operational_complexity),
            ("linkedin_url", parsed.linkedin_url),
            ("notes", parsed.notes),
        )
        if value is not None
    }
    current = {field_name: getattr(account, field_name) for field_name in update}
    changes = changed_fields(current, update)
    for field_name, value in changes.items():
        _apply_manual_value(account, field_name, value)
    return changes


async def import_accounts(
    session: AsyncSession,
    *,
    file_text: str,
    dry_run: bool,
    import_max_rows: int,
    actor_id: uuid.UUID,
    now: datetime,
) -> ImportResultData:
    """`API-22`, `S-ACC-02`. Raises `ImportTooLarge` when the file has more than
    `import_max_rows` rows; writes nothing in that case, and nothing at all when `dry_run` is
    true."""
    raw_rows = parse_csv_rows(file_text)
    if len(raw_rows) > import_max_rows:
        raise ImportTooLarge("file", f"The file has more than {import_max_rows} rows.")

    active_industry_codes = frozenset(
        (
            await session.execute(
                select(Industry.code).where(Industry.status == IndustryStatus.ACTIVE)
            )
        )
        .scalars()
        .all()
    )

    row_results: list[ImportRowResult] = []
    created = updated = duplicates = invalid = 0

    for line, raw in enumerate(raw_rows, start=2):  # the header row is line 1
        parsed = parse_import_row(line, raw, active_industry_codes)
        if parsed.errors:
            invalid += 1
            row_results.append(
                ImportRowResult(
                    line=line,
                    domain=parsed.domain or raw.get("domain") or None,
                    outcome=ImportRowOutcome.INVALID,
                    account_id=None,
                    errors=tuple((e.field, e.message) for e in parsed.errors),
                )
            )
            continue

        assert parsed.domain is not None and parsed.name is not None

        existing_account = await _find_account_by_domain(session, parsed.domain)
        if existing_account is not None:
            if not dry_run:
                changes = _apply_import_row_update(existing_account, parsed)
                for alias in parsed.aliases:
                    await _write_alias(session, existing_account.id, alias)
                for source in parsed.sources:
                    await _write_source(session, existing_account.id, source.kind, source.url)
                if changes:
                    await append_audit_event(
                        session,
                        action=AuditAction.ACCOUNT_UPDATED,
                        occurred_at=now,
                        actor_id=actor_id,
                        entity_type="account",
                        entity_id=existing_account.id,
                        payload={
                            field_name: _dump_value(value) for field_name, value in changes.items()
                        },
                    )
                    await _enqueue_account_change_rescores(
                        session, account_id=existing_account.id, actor_id=actor_id, now=now
                    )
            updated += 1
            row_results.append(
                ImportRowResult(
                    line=line,
                    domain=parsed.domain,
                    outcome=ImportRowOutcome.UPDATED,
                    account_id=existing_account.id,
                    errors=(),
                )
            )
            continue

        duplicate_account = await _find_account_by_name_match(session, parsed.name)
        if duplicate_account is not None:
            duplicates += 1
            row_results.append(
                ImportRowResult(
                    line=line,
                    domain=parsed.domain,
                    outcome=ImportRowOutcome.POSSIBLE_DUPLICATE,
                    account_id=duplicate_account.id,
                    errors=(),
                )
            )
            continue

        new_account_id: uuid.UUID | None = None
        if not dry_run:
            new_account = await _insert_new_account(
                session,
                domain=parsed.domain,
                name=parsed.name,
                origin=AccountOrigin.IMPORTED,
                country_code=parsed.country_code,
                industry=parsed.industry,
                employee_count=parsed.employee_count,
                revenue_eur=parsed.revenue_eur,
                operational_complexity=parsed.operational_complexity,
                linkedin_url=parsed.linkedin_url,
                notes=parsed.notes,
                aliases=parsed.aliases,
                sources=tuple((s.kind, s.url) for s in parsed.sources),
            )
            new_account_id = new_account.id
            await append_audit_event(
                session,
                action=AuditAction.ACCOUNT_CREATED,
                occurred_at=now,
                actor_id=actor_id,
                entity_type="account",
                entity_id=new_account.id,
                payload={"domain": parsed.domain, "origin": AccountOrigin.IMPORTED.value},
            )
        created += 1
        row_results.append(
            ImportRowResult(
                line=line,
                domain=parsed.domain,
                outcome=ImportRowOutcome.CREATED,
                account_id=new_account_id,
                errors=(),
            )
        )

    if not dry_run:
        await append_audit_event(
            session,
            action=AuditAction.ACCOUNTS_IMPORTED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type=None,
            entity_id=None,
            payload={
                "rows": len(raw_rows),
                "created": created,
                "updated": updated,
                "duplicates": duplicates,
                "invalid": invalid,
            },
        )
        await session.commit()

    return ImportResultData(
        dry_run=dry_run,
        rows=tuple(row_results),
        created=created,
        updated=updated,
        duplicates=duplicates,
        invalid=invalid,
    )
