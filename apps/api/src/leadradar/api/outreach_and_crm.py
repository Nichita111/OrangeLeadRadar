"""Router of the [Outreach and CRM](/architecture/interfaces.md#outreach-and-crm) family:
`API-56` to `API-59`. The drafts (`API-56` to `API-58`, `S-OUT-01`) are
`leadradar.outreach.drafts`; the HubSpot push (`API-59`) is `leadradar.outreach.commands`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.ai.shapes import OutreachPreferences
from leadradar.api.authentication import CurrentUser
from leadradar.core.enums import (
    CrmSyncStatus,
    CrmSyncTarget,
    EngagementOrigin,
    EngagementStatus,
    OutreachDraftChannel,
    OutreachDraftStatus,
    ProviderFactStatus,
    ToneVerdict,
)
from leadradar.db.models.configuration import ProviderFact as ProviderFactRow
from leadradar.db.models.configuration import Service
from leadradar.db.session import get_session
from leadradar.outreach.commands import push_to_crm
from leadradar.outreach.drafts import (
    DraftView,
    EngagementView,
    check_tone,
    create_draft,
    list_drafts,
    mark_contacted,
    update_draft,
)
from leadradar.outreach.errors import OutreachValidationError

router = APIRouter(tags=["outreach-and-crm"])


class OutreachRequest(BaseModel):
    """[`OutreachRequest`](/architecture/interfaces.md#outreachrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: OutreachDraftChannel
    contact_id: str | SkipJsonSchema[None] = None
    preferences: OutreachPreferences | SkipJsonSchema[None] = None


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


class OutreachDraftProviderFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    text: str


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
    preferences: OutreachPreferences | None
    contact: OutreachDraftContact | None
    findings: list[OutreachDraftFinding]
    provider_facts: list[OutreachDraftProviderFact]
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


class ToneCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str | None
    body: str


class ToneNote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    phrase: str
    suggested_rewrite: str


class ToneCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: ToneVerdict
    summary: str
    notes: list[ToneNote]


class EngagementStatusView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    service_id: uuid.UUID
    status: EngagementStatus
    origin: EngagementOrigin
    occurred_at: datetime
    note: str | None
    created_at: datetime
    set_by_name: str | None


class ProviderFactService(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    name: str


class ProviderFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    text: str
    source_url: str | None
    services: list[ProviderFactService]
    status: ProviderFactStatus
    created_at: datetime
    updated_at: datetime


@router.get("/provider-facts", response_model=list[ProviderFact])
async def get_provider_facts(
    session: Annotated[AsyncSession, Depends(get_session)],
    _principal: CurrentUser,
    status: Annotated[ProviderFactStatus | None, Query()] = ProviderFactStatus.ACTIVE,
    service_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ProviderFact]:
    """`API-79`: active facts applicable to the selected service."""
    rows = (
        (
            await session.execute(
                select(ProviderFactRow).order_by(
                    ProviderFactRow.created_at.desc(), ProviderFactRow.id
                )
            )
        )
        .scalars()
        .all()
    )
    if status is not None:
        rows = [row for row in rows if row.status == status]
    if service_id is not None:
        rows = [row for row in rows if not row.service_ids or service_id in row.service_ids]
        rows.sort(key=lambda row: service_id not in row.service_ids)
    service_ids = {item for row in rows for item in row.service_ids}
    service_rows = (
        (await session.execute(select(Service).where(Service.id.in_(list(service_ids)))))
        .scalars()
        .all()
    )
    services = {row.id: row.name for row in service_rows}
    return [
        ProviderFact(
            id=row.id,
            text=row.text,
            source_url=row.source_url,
            services=[
                ProviderFactService(id=item, name=services[item])
                for item in row.service_ids
                if item in services
            ],
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


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
        preferences=view.preferences,
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
        provider_facts=[
            OutreachDraftProviderFact(id=str(f.id), text=f.text) for f in view.provider_facts
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
        preferences=payload.preferences,
        gateway=request.app.state.ai_gateway,
        max_findings=settings.outreach_max_findings,
        max_provider_facts=settings.provider_facts_per_call,
        max_chars=(
            settings.outreach_email_max_chars
            if channel == OutreachDraftChannel.EMAIL
            else settings.outreach_inmail_max_chars
        ),
        principal=principal,
        now=request.app.state.clock(),
    )
    return _to_outreach_draft(view)


@router.post("/outreach-drafts/{id}/tone-check", response_model=ToneCheck)
async def post_tone_check(
    id: uuid.UUID,
    payload: ToneCheckRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> ToneCheck:
    """`API-91`: advisory check of current editor text through the AI gateway."""
    result = await check_tone(
        session,
        draft_id=id,
        subject=payload.subject,
        body=payload.body,
        gateway=request.app.state.ai_gateway,
        actor_id=principal.id,
    )
    return ToneCheck(
        verdict=result.verdict,
        summary=result.summary,
        notes=[ToneNote(**note.model_dump()) for note in result.notes],
    )


def _engagement(view: EngagementView) -> EngagementStatusView:
    return EngagementStatusView(
        id=view.id,
        service_id=view.service_id,
        status=view.status,
        origin=view.origin,
        occurred_at=view.occurred_at,
        note=view.note,
        created_at=view.created_at,
        set_by_name=view.set_by_name,
    )


@router.post("/outreach-drafts/{id}/mark-contacted", response_model=EngagementStatusView)
async def post_mark_contacted(
    id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> EngagementStatusView:
    """`API-93`: atomically mark an exported draft contacted."""
    return _engagement(
        await mark_contacted(
            session,
            draft_id=id,
            principal=principal,
            now=request.app.state.clock(),
        )
    )


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
