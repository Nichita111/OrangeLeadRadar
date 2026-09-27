"""Reads that shape [`AccountRow`](/architecture/interfaces.md#accountrow) and
[`Account`](/architecture/interfaces.md#account) (`API-20`, `API-23`) out of the store, and the
plain input shapes `accounts.commands` takes for a source. Plain dataclasses, not Pydantic
models: those live at the api boundary (`api/accounts.py`), which shapes its response from
these."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AccountOperationalComplexity,
    AccountOrigin,
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AccountStatus,
    PipelineRunKind,
    PipelineRunStatus,
)
from leadradar.db.models.accounts import Account, AccountAlias, AccountSource
from leadradar.db.models.ingestion import PipelineRun

_ACTIVE_RUN_STATUSES = (PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING)


@dataclass(frozen=True)
class NewSourceInput:
    """One entry of [`AccountCreate`](/architecture/interfaces.md#accountcreate) `sources`
    (`API-21`)."""

    kind: AccountSourceKind
    url: str


@dataclass(frozen=True)
class SourceUpdateInput:
    """One entry of [`AccountUpdate`](/architecture/interfaces.md#accountupdate) `sources`
    (`API-24`)."""

    kind: AccountSourceKind
    url: str
    status: AccountSourceStatus


@dataclass(frozen=True)
class ParentSummary:
    """`Account.parent`."""

    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class SourceData:
    """One entry of `Account.sources`."""

    url: str
    kind: AccountSourceKind
    origin: AccountSourceOrigin
    status: AccountSourceStatus


@dataclass(frozen=True)
class AccountRowData:
    """[`AccountRow`](/architecture/interfaces.md#accountrow), one row of `API-20`."""

    id: uuid.UUID
    name: str
    domain: str
    country_code: str | None
    industry: str | None
    status: AccountStatus
    origin: AccountOrigin
    last_refreshed_at: datetime | None
    active_run_id: uuid.UUID | None


@dataclass(frozen=True)
class AccountData:
    """[`Account`](/architecture/interfaces.md#account), the response of `API-21`, `API-23` and
    `API-24`."""

    row: AccountRowData
    employee_count: int | None
    revenue_eur: int | None
    operational_complexity: AccountOperationalComplexity | None
    attribute_origin: dict[str, str]
    parent: ParentSummary | None
    crunchbase_id: str | None
    linkedin_url: str | None
    notes: str | None
    aliases: tuple[str, ...]
    sources: tuple[SourceData, ...]
    next_refresh_at: datetime | None


@dataclass(frozen=True)
class PageData[ItemT]:
    """`Page<T>` ([Conventions](/architecture/interfaces.md#conventions) Pagination)."""

    items: tuple[ItemT, ...]
    page: int
    page_size: int
    total: int


async def _active_run_ids(
    session: AsyncSession, account_ids: list[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    """The id of each account's `QUEUED` or `RUNNING` `ACCOUNT_REFRESH` run, when there is one.
    At most one such run exists per account ([Constraints and indexes]
    (/architecture/sql-store.md#constraints-and-indexes))."""
    if not account_ids:
        return {}
    rows = (
        await session.execute(
            select(PipelineRun.account_id, PipelineRun.id).where(
                PipelineRun.kind == PipelineRunKind.ACCOUNT_REFRESH,
                PipelineRun.status.in_(_ACTIVE_RUN_STATUSES),
                PipelineRun.account_id.in_(account_ids),
            )
        )
    ).all()
    return {account_id: run_id for account_id, run_id in rows if account_id is not None}


def _row_data(account: Account, active_run_id: uuid.UUID | None) -> AccountRowData:
    return AccountRowData(
        id=account.id,
        name=account.name,
        domain=account.domain,
        country_code=account.country_code,
        industry=account.industry,
        status=account.status,
        origin=account.origin,
        last_refreshed_at=account.last_refreshed_at,
        active_run_id=active_run_id,
    )


async def list_accounts(
    session: AsyncSession,
    *,
    q: str | None,
    status: AccountStatus | None,
    country_code: str | None,
    industry: str | None,
    origin: AccountOrigin | None,
    page: int,
    page_size: int,
) -> PageData[AccountRowData]:
    """`API-20`: `q` matches the name, any alias or the domain ([Accounts and contacts]
    (/architecture/interfaces.md#accounts-and-contacts))."""
    filters = []
    if status is not None:
        filters.append(Account.status == status)
    if country_code is not None:
        filters.append(Account.country_code == country_code)
    if industry is not None:
        filters.append(Account.industry == industry)
    if origin is not None:
        filters.append(Account.origin == origin)
    if q:
        pattern = f"%{q}%"
        filters.append(
            or_(
                Account.name.ilike(pattern),
                Account.domain.ilike(pattern),
                Account.id.in_(
                    select(AccountAlias.account_id).where(AccountAlias.alias.ilike(pattern))
                ),
            )
        )

    base = select(Account)
    for condition in filters:
        base = base.where(condition)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    rows = (
        (
            await session.execute(
                base.order_by(Account.name).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    active_runs = await _active_run_ids(session, [row.id for row in rows])
    items = tuple(_row_data(row, active_runs.get(row.id)) for row in rows)
    return PageData(items=items, page=page, page_size=page_size, total=total)


async def account_data(session: AsyncSession, account: Account) -> AccountData:
    """Assembles [`Account`](/architecture/interfaces.md#account) for one already-loaded
    `account` row."""
    active_runs = await _active_run_ids(session, [account.id])

    aliases = (
        (
            await session.execute(
                select(AccountAlias.alias).where(AccountAlias.account_id == account.id)
            )
        )
        .scalars()
        .all()
    )

    sources = (
        (await session.execute(select(AccountSource).where(AccountSource.account_id == account.id)))
        .scalars()
        .all()
    )

    parent: ParentSummary | None = None
    if account.parent_account_id is not None:
        parent_row = (
            await session.execute(
                select(Account.id, Account.name).where(Account.id == account.parent_account_id)
            )
        ).first()
        if parent_row is not None:
            parent = ParentSummary(id=parent_row[0], name=parent_row[1])

    return AccountData(
        row=_row_data(account, active_runs.get(account.id)),
        employee_count=account.employee_count,
        revenue_eur=account.revenue_eur,
        operational_complexity=account.operational_complexity,
        attribute_origin={k: str(v) for k, v in account.attribute_origin.items()},
        parent=parent,
        crunchbase_id=account.crunchbase_id,
        linkedin_url=account.linkedin_url,
        notes=account.notes,
        aliases=tuple(aliases),
        sources=tuple(
            SourceData(url=s.url, kind=s.kind, origin=s.origin, status=s.status) for s in sources
        ),
        next_refresh_at=account.next_refresh_at,
    )
