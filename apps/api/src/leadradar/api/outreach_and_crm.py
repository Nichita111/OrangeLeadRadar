"""Router of the [Outreach and CRM](/architecture/interfaces.md#outreach-and-crm) family:
`API-56` to `API-59`. The drafts (`API-56` to `API-58`, `S-OUT-01`) are
`leadradar.outreach.drafts`; the HubSpot push (`API-59`) is `leadradar.outreach.commands`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import CurrentUser
from leadradar.core.enums import (
    CrmSyncStatus,
    CrmSyncTarget,
    OutreachDraftChannel,
    OutreachDraftStatus,
)
from leadradar.db.session import get_session
from leadradar.outreach.commands import push_to_crm
from leadradar.outreach.drafts import DraftView, create_draft, list_drafts, update_draft
from leadradar.outreach.errors import OutreachValidationError

router = APIRouter(tags=["outreach-and-crm"])


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


def _to_outreach_draft(view: DraftView) -> OutreachDraft:
    return OutreachDraft(
        id=str(view.id),
        account_id=str(view.account_id),
        service_id=str(view.service_id),
        subject=view.subject,
        body=view.body,
        edited=view.edited,
        created_at=view.created_at.isoformat(),
        channel=view.channel,
        status=view.status,
        contact=(
            None
            if view.contact is None
            else OutreachDraftContact(
                id=str(view.contact.id),
                full_name=view.contact.full_name,
                job_title=view.contact.job_title,
            )
        ),
        findings=[
            OutreachDraftFinding(id=str(f.id), question_text=f.question_text, quote=f.quote)
            for f in view.findings
        ],
        created_by_name=view.created_by_name,
    )


@router.post("/accounts/{id}/scores/{service_id}/outreach-drafts", response_model=OutreachDraft)
async def create_outreach_draft(
    id: uuid.UUID,
    service_id: uuid.UUID,
    payload: OutreachRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> OutreachDraft:
    """`API-56`: follows [Outreach grounding](/architecture/rules.md#outreach-grounding); nothing
    is sent."""
    settings = request.app.state.settings
    channel = payload.channel
    view = await create_draft(
        session,
        account_id=id,
        service_id=service_id,
        channel=channel,
        contact_id=_contact_id(payload.contact_id),
        gateway=request.app.state.ai_gateway,
        max_findings=settings.outreach_max_findings,
        max_chars=(
            settings.outreach_email_max_chars
            if channel == OutreachDraftChannel.EMAIL
            else settings.outreach_inmail_max_chars
        ),
        principal=principal,
        now=request.app.state.clock(),
    )
    return _to_outreach_draft(view)


@router.get("/accounts/{id}/outreach-drafts", response_model=list[OutreachDraft])
async def list_outreach_drafts(
    id: uuid.UUID,
    service_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _principal: CurrentUser,
) -> list[OutreachDraft]:
    """`API-57`."""
    return [_to_outreach_draft(view) for view in await list_drafts(session, id, service_id)]


@router.patch("/outreach-drafts/{id}", response_model=OutreachDraft)
async def update_outreach_draft(
    id: uuid.UUID,
    payload: OutreachDraftUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> OutreachDraft:
    """`API-58`: changing `subject` or `body` sets `edited`; `status` may only move to
    `EXPORTED`."""
    view = await update_draft(
        session,
        draft_id=id,
        subject=payload.subject,
        body=payload.body,
        status=payload.status,
        actor_id=principal.id,
        now=request.app.state.clock(),
    )
    return _to_outreach_draft(view)


def _contact_id(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise OutreachValidationError("contact_id", "Not a contact id.") from None
