"""Router of the [Outreach and CRM](/architecture/interfaces.md#outreach-and-crm) family:
`API-56` to `API-59`. `API-59` is built; `API-56` to `API-58` are declared stubs answering
`501 NOT_IMPLEMENTED` until `S-OUT-01`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import CurrentUser
from leadradar.api.router_utils import stub_router
from leadradar.core.enums import (
    CrmSyncStatus,
    CrmSyncTarget,
    OutreachDraftChannel,
    OutreachDraftStatus,
)
from leadradar.db.session import get_session
from leadradar.outreach.commands import push_to_crm

router = APIRouter(tags=["outreach-and-crm"])
outreach_stub_router = stub_router("outreach-and-crm")


class OutreachRequest(BaseModel):
    """[`OutreachRequest`](/architecture/interfaces.md#outreachrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: OutreachDraftChannel
    contact_id: str | SkipJsonSchema[None] = None


class OutreachDraftContact(BaseModel):
    """`OutreachDraft.contact`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    full_name: str
    job_title: str


class OutreachDraftFinding(BaseModel):
    """One entry of `OutreachDraft.findings`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question_text: str
    quote: str


class OutreachDraft(BaseModel):
    """[`OutreachDraft`](/architecture/interfaces.md#outreachdraft)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    account_id: str
    service_id: str
    subject: str | None
    body: str
    edited: bool
    created_at: str
    channel: OutreachDraftChannel
    status: OutreachDraftStatus
    contact: OutreachDraftContact | None
    findings: list[OutreachDraftFinding]
    created_by_name: str


class OutreachDraftUpdate(BaseModel):
    """[`OutreachDraftUpdate`](/architecture/interfaces.md#outreachdraftupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str | SkipJsonSchema[None] = None
    body: str | SkipJsonSchema[None] = None
    status: OutreachDraftStatus | SkipJsonSchema[None] = None


class CrmSyncView(BaseModel):
    """[`CrmSyncView`](/architecture/interfaces.md#crmsyncview), the response of `API-59`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    external_id: str | None
    error: str | None
    created_at: datetime
    target: CrmSyncTarget
    status: CrmSyncStatus


@router.post("/accounts/{id}/scores/{service_id}/crm-push")
async def post_crm_push(
    id: uuid.UUID,
    service_id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> CrmSyncView:
    """`API-59`: pushes the account's current score for the service to HubSpot and records the
    outcome in [`crm_sync`](/architecture/sql-store.md#crm_sync)."""
    settings = request.app.state.settings
    result = await push_to_crm(
        session,
        account_id=id,
        service_id=service_id,
        principal=principal,
        settings=settings,
        http=request.app.state.http_client,
        now=request.app.state.clock(),
    )
    return CrmSyncView(
        id=result.id,
        external_id=result.external_id,
        error=result.error,
        created_at=result.created_at,
        target=result.target,
        status=result.status,
    )


@outreach_stub_router.post(
    "/accounts/{id}/scores/{service_id}/outreach-drafts", response_model=OutreachDraft
)
async def create_outreach_draft(
    id: str, service_id: str, payload: OutreachRequest
) -> OutreachDraft:
    """`API-56`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@outreach_stub_router.get("/accounts/{id}/outreach-drafts", response_model=list[OutreachDraft])
async def list_outreach_drafts(id: str, service_id: str) -> list[OutreachDraft]:
    """`API-57`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@outreach_stub_router.patch("/outreach-drafts/{id}", response_model=OutreachDraft)
async def update_outreach_draft(id: str, payload: OutreachDraftUpdate) -> OutreachDraft:
    """`API-58`."""
    raise AssertionError("unreachable: contract_not_built already raised")
