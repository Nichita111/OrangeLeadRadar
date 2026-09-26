"""Router of the [Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts)
family, its accounts half: `API-20` to `API-22` and `API-24`. Only `API-23` (`GET
/accounts/{id}`) is added alongside them, since `Account` is also `API-21`'s and `API-24`'s
response; contacts (`API-25` to `API-28`) are a later task."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.commands import (
    AccountCreateData,
    AccountUpdateData,
    create_account,
    import_accounts,
    update_account,
)
from leadradar.accounts.errors import AccountNotFound, AccountValidationError, InvalidImportFile
from leadradar.accounts.queries import (
    AccountData,
    AccountRowData,
    NewSourceInput,
    SourceUpdateInput,
    account_data,
    list_accounts,
)
from leadradar.api.authentication import CurrentUser
from leadradar.core.enums import (
    AccountOperationalComplexity,
    AccountOrigin,
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AccountStatus,
)
from leadradar.db.models.accounts import Account as AccountModel
from leadradar.db.session import get_session

router = APIRouter(tags=["accounts-and-contacts"])


class Page[ItemT](BaseModel):
    """`Page<T>` ([Conventions](/architecture/interfaces.md#conventions) Pagination)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ItemT]
    page: int
    page_size: int
    total: int


class AccountRow(BaseModel):
    """[`AccountRow`](/architecture/interfaces.md#accountrow), one item of `API-20`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    name: str
    domain: str
    country_code: str | None
    industry: str | None
    status: AccountStatus
    origin: AccountOrigin
    last_refreshed_at: datetime | None
    active_run_id: uuid.UUID | None


class AccountParent(BaseModel):
    """`Account.parent`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    name: str


class AccountSourceItem(BaseModel):
    """One entry of `Account.sources`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    kind: AccountSourceKind
    origin: AccountSourceOrigin
    status: AccountSourceStatus


class Account(BaseModel):
    """[`Account`](/architecture/interfaces.md#account), the response of `API-21`, `API-23` and
    `API-24`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    name: str
    domain: str
    country_code: str | None
    industry: str | None
    status: AccountStatus
    origin: AccountOrigin
    last_refreshed_at: datetime | None
    active_run_id: uuid.UUID | None
    employee_count: int | None
    revenue_eur: int | None
    operational_complexity: AccountOperationalComplexity | None
    attribute_origin: dict[str, str]
    parent: AccountParent | None
    crunchbase_id: str | None
    linkedin_url: str | None
    notes: str | None
    aliases: list[str]
    sources: list[AccountSourceItem]
    next_refresh_at: datetime | None


class AccountCreateSource(BaseModel):
    """One entry of [`AccountCreate`](/architecture/interfaces.md#accountcreate) `sources`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: AccountSourceKind
    url: str


class AccountCreate(BaseModel):
    """[`AccountCreate`](/architecture/interfaces.md#accountcreate), the request of `API-21`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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
    aliases: list[str] = []
    sources: list[AccountCreateSource] = []


class AccountUpdateSource(BaseModel):
    """One entry of [`AccountUpdate`](/architecture/interfaces.md#accountupdate) `sources`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: AccountSourceKind
    url: str
    status: AccountSourceStatus = AccountSourceStatus.ACTIVE


class AccountUpdate(BaseModel):
    """[`AccountUpdate`](/architecture/interfaces.md#accountupdate), the request of `API-24`.
    Every field of [`AccountCreate`](#accountcreate) except `domain`, optional, plus `status`; a
    field left unset changes nothing ([`AccountUpdateData`](../accounts/commands.py))."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    country_code: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue_eur: int | None = None
    operational_complexity: AccountOperationalComplexity | None = None
    parent_account_id: uuid.UUID | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    status: AccountStatus | None = None
    aliases: list[str] | None = None
    sources: list[AccountUpdateSource] | None = None


class ImportRowFieldError(BaseModel):
    """One entry of an import row's `errors`, in the shape of `details.fields[]`
    ([Conventions](/architecture/interfaces.md#conventions) Envelope)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    message: str


class ImportRowItem(BaseModel):
    """One entry of `ImportResult.rows`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    line: int
    domain: str | None
    outcome: str
    account_id: uuid.UUID | None
    errors: list[ImportRowFieldError]


class ImportResult(BaseModel):
    """[`ImportResult`](/architecture/interfaces.md#importresult), the response of `API-22`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dry_run: bool
    rows: list[ImportRowItem]
    created: int
    updated: int
    duplicates: int
    invalid: int


def _to_account_row(row: AccountRowData) -> AccountRow:
    return AccountRow(
        id=row.id,
        name=row.name,
        domain=row.domain,
        country_code=row.country_code,
        industry=row.industry,
        status=row.status,
        origin=row.origin,
        last_refreshed_at=row.last_refreshed_at,
        active_run_id=row.active_run_id,
    )


def _to_account(data: AccountData) -> Account:
    return Account(
        id=data.row.id,
        name=data.row.name,
        domain=data.row.domain,
        country_code=data.row.country_code,
        industry=data.row.industry,
        status=data.row.status,
        origin=data.row.origin,
        last_refreshed_at=data.row.last_refreshed_at,
        active_run_id=data.row.active_run_id,
        employee_count=data.employee_count,
        revenue_eur=data.revenue_eur,
        operational_complexity=data.operational_complexity,
        attribute_origin=data.attribute_origin,
        parent=(
            AccountParent(id=data.parent.id, name=data.parent.name)
            if data.parent is not None
            else None
        ),
        crunchbase_id=data.crunchbase_id,
        linkedin_url=data.linkedin_url,
        notes=data.notes,
        aliases=list(data.aliases),
        sources=[
            AccountSourceItem(url=s.url, kind=s.kind, origin=s.origin, status=s.status)
            for s in data.sources
        ],
        next_refresh_at=data.next_refresh_at,
    )


@router.get("/accounts")
async def get_accounts(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    _principal: CurrentUser,
    q: str | None = None,
    status: AccountStatus | None = None,
    country_code: str | None = None,
    industry: str | None = None,
    origin: AccountOrigin | None = None,
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
) -> Page[AccountRow]:
    """`API-20`: `q` matches the name, any alias or the domain."""
    settings = request.app.state.settings
    effective_page_size = page_size or settings.page_size_default
    if effective_page_size > settings.page_size_max:
        raise AccountValidationError(
            "page_size", f"page_size must be at most {settings.page_size_max}."
        )
    result = await list_accounts(
        session,
        q=q,
        status=status,
        country_code=country_code,
        industry=industry,
        origin=origin,
        page=page,
        page_size=effective_page_size,
    )
    return Page(
        items=[_to_account_row(row) for row in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
    )


@router.post("/accounts")
async def post_account(
    body: AccountCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> Account:
    """`API-21`."""
    data = AccountCreateData(
        domain=body.domain,
        name=body.name,
        country_code=body.country_code,
        industry=body.industry,
        employee_count=body.employee_count,
        revenue_eur=body.revenue_eur,
        operational_complexity=body.operational_complexity,
        parent_account_id=body.parent_account_id,
        linkedin_url=body.linkedin_url,
        notes=body.notes,
        aliases=tuple(body.aliases),
        sources=tuple(NewSourceInput(kind=s.kind, url=s.url) for s in body.sources),
    )
    result = await create_account(
        session, data=data, actor_id=principal.id, now=request.app.state.clock()
    )
    return _to_account(result)


@router.post("/accounts/import")
async def post_accounts_import(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()],
) -> ImportResult:
    """`API-22`: multipart `file` ([`AccountImportRow`](
    /architecture/interfaces.md#accountimportrow) CSV) and `dry_run`."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidImportFile("file", "The file must be UTF-8 encoded.") from exc

    result = await import_accounts(
        session,
        file_text=text,
        dry_run=dry_run,
        import_max_rows=request.app.state.settings.import_max_rows,
        actor_id=principal.id,
        now=request.app.state.clock(),
    )
    return ImportResult(
        dry_run=result.dry_run,
        rows=[
            ImportRowItem(
                line=row.line,
                domain=row.domain,
                outcome=row.outcome.value,
                account_id=row.account_id,
                errors=[ImportRowFieldError(field=f, message=m) for f, m in row.errors],
            )
            for row in result.rows
        ],
        created=result.created,
        updated=result.updated,
        duplicates=result.duplicates,
        invalid=result.invalid,
    )


@router.get("/accounts/{id}")
async def get_account(
    id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _principal: CurrentUser,
) -> Account:
    """`API-23`."""
    account = (
        await session.execute(select(AccountModel).where(AccountModel.id == id))
    ).scalar_one_or_none()
    if account is None:
        raise AccountNotFound(f"No account {id}.")
    result = await account_data(session, account)
    return _to_account(result)


@router.patch("/accounts/{id}")
async def patch_account(
    id: uuid.UUID,
    body: AccountUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> Account:
    """`API-24`."""
    data = AccountUpdateData(
        country_code=body.country_code,
        industry=body.industry,
        employee_count=body.employee_count,
        revenue_eur=body.revenue_eur,
        operational_complexity=body.operational_complexity,
        parent_account_id=body.parent_account_id,
        linkedin_url=body.linkedin_url,
        notes=body.notes,
        status=body.status,
        aliases=tuple(body.aliases) if body.aliases is not None else None,
        sources=(
            tuple(SourceUpdateInput(kind=s.kind, url=s.url, status=s.status) for s in body.sources)
            if body.sources is not None
            else None
        ),
    )
    result = await update_account(
        session,
        account_id=id,
        data=data,
        actor_id=principal.id,
        now=request.app.state.clock(),
    )
    return _to_account(result)
