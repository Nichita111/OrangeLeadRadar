"""Router of the [Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts)
family: `API-20` to `API-28`. Every route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from typing import Literal

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, ConfigDict

from leadradar.api.common import Page
from leadradar.api.router_utils import stub_router
from leadradar.core.enums import (
    AccountOperationalComplexity,
    AccountOrigin,
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AccountStatus,
    ContactPersona,
    ContactPersonaOrigin,
)

router = stub_router("accounts-and-contacts")


class AccountRow(BaseModel):
    """[`AccountRow`](/architecture/interfaces.md#accountrow)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    domain: str
    country_code: str
    industry: str | None
    status: AccountStatus
    origin: AccountOrigin
    last_refreshed_at: str | None
    active_run_id: str | None


class AccountSource(BaseModel):
    """One entry of `Account.sources`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    kind: AccountSourceKind
    origin: AccountSourceOrigin
    status: AccountSourceStatus


class AccountParent(BaseModel):
    """`Account.parent`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str


class Account(AccountRow):
    """[`Account`](/architecture/interfaces.md#account): every field of
    [`AccountRow`](#accountrow) plus these."""

    employee_count: int | None
    revenue_eur: int | None
    operational_complexity: AccountOperationalComplexity | None
    attribute_origin: dict[str, str]
    parent: AccountParent | None
    crunchbase_id: str | None
    linkedin_url: str | None
    notes: str | None
    aliases: list[str]
    sources: list[AccountSource]
    next_refresh_at: str | None


class AccountSourceCreate(BaseModel):
    """One entry of `AccountCreate.sources`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: AccountSourceKind
    url: str


class AccountCreate(BaseModel):
    """[`AccountCreate`](/architecture/interfaces.md#accountcreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: str
    name: str
    country_code: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue_eur: int | None = None
    operational_complexity: AccountOperationalComplexity | None = None
    parent_account_id: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    aliases: list[str] | None = None
    sources: list[AccountSourceCreate] | None = None


class AccountSourceUpdate(BaseModel):
    """One entry of `AccountUpdate.sources`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: AccountSourceKind
    url: str
    status: AccountSourceStatus | None = None


class AccountUpdate(BaseModel):
    """[`AccountUpdate`](/architecture/interfaces.md#accountupdate): every field of
    [`AccountCreate`](#accountcreate) except `domain`, optional, plus `sources` and `status`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = None
    country_code: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue_eur: int | None = None
    operational_complexity: AccountOperationalComplexity | None = None
    parent_account_id: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    aliases: list[str] | None = None
    sources: list[AccountSourceUpdate] | None = None
    status: AccountStatus | None = None


class ImportRowResult(BaseModel):
    """One entry of `ImportResult.rows`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    line: int
    domain: str
    outcome: Literal["CREATED", "UPDATED", "POSSIBLE_DUPLICATE", "INVALID"]
    account_id: str | None
    errors: list[dict[str, str]]


class ImportResult(BaseModel):
    """[`ImportResult`](/architecture/interfaces.md#importresult)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dry_run: bool
    rows: list[ImportRowResult]
    created: int
    updated: int
    duplicates: int
    invalid: int


class Contact(BaseModel):
    """[`Contact`](/architecture/interfaces.md#contact)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    account_id: str
    full_name: str
    job_title: str
    source_url: str
    persona: ContactPersona
    persona_origin: ContactPersonaOrigin
    retain_until: str


class ContactCreate(BaseModel):
    """[`ContactCreate`](/architecture/interfaces.md#contactcreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    full_name: str
    job_title: str
    source_url: str
    persona: ContactPersona | None = None


class ContactUpdate(BaseModel):
    """[`ContactUpdate`](/architecture/interfaces.md#contactupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    full_name: str | None = None
    job_title: str | None = None
    source_url: str | None = None
    persona: ContactPersona | None = None


@router.get("/accounts", response_model=Page[AccountRow])
async def list_accounts(
    q: str | None = None,
    status: AccountStatus | None = None,
    country_code: str | None = None,
    industry: str | None = None,
    origin: AccountOrigin | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> Page[AccountRow]:
    """`API-20`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/accounts", response_model=Account)
async def create_account(payload: AccountCreate) -> Account:
    """`API-21`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/accounts/import", response_model=ImportResult)
async def import_accounts(file: UploadFile = File(...), dry_run: bool = Form(...)) -> ImportResult:
    """`API-22`. `AccountImportRow` describes the uploaded CSV's columns."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/accounts/{id}", response_model=Account)
async def get_account(id: str) -> Account:
    """`API-23`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/accounts/{id}", response_model=Account)
async def update_account(id: str, payload: AccountUpdate) -> Account:
    """`API-24`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/accounts/{id}/contacts", response_model=list[Contact])
async def list_contacts(id: str) -> list[Contact]:
    """`API-25`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/accounts/{id}/contacts", response_model=Contact)
async def create_contact(id: str, payload: ContactCreate) -> Contact:
    """`API-26`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/contacts/{id}", response_model=Contact)
async def update_contact(id: str, payload: ContactUpdate) -> Contact:
    """`API-27`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.delete("/contacts/{id}", status_code=204)
async def delete_contact(id: str) -> None:
    """`API-28`."""
    raise AssertionError("unreachable: contract_not_built already raised")
