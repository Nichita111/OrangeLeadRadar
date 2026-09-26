"""Router of the [Outreach and CRM](/architecture/interfaces.md#outreach-and-crm) family:
`API-56` to `API-59`. Every route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from leadradar.api.router_utils import stub_router
from leadradar.core.enums import (
    CrmSyncStatus,
    CrmSyncTarget,
    OutreachDraftChannel,
    OutreachDraftStatus,
)

router = stub_router("outreach-and-crm")


class OutreachRequest(BaseModel):
    """[`OutreachRequest`](/architecture/interfaces.md#outreachrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: OutreachDraftChannel
    contact_id: str | None = None


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

    subject: str | None = None
    body: str | None = None
    status: OutreachDraftStatus | None = None


class CrmSyncView(BaseModel):
    """[`CrmSyncView`](/architecture/interfaces.md#crmsyncview)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    external_id: str | None
    error: str | None
    created_at: str
    target: CrmSyncTarget
    status: CrmSyncStatus


@router.post("/accounts/{id}/scores/{service_id}/outreach-drafts", response_model=OutreachDraft)
async def create_outreach_draft(
    id: str, service_id: str, payload: OutreachRequest
) -> OutreachDraft:
    """`API-56`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/accounts/{id}/outreach-drafts", response_model=list[OutreachDraft])
async def list_outreach_drafts(id: str, service_id: str) -> list[OutreachDraft]:
    """`API-57`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/outreach-drafts/{id}", response_model=OutreachDraft)
async def update_outreach_draft(id: str, payload: OutreachDraftUpdate) -> OutreachDraft:
    """`API-58`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/accounts/{id}/scores/{service_id}/crm-push", response_model=CrmSyncView)
async def push_to_crm(id: str, service_id: str) -> CrmSyncView:
    """`API-59`."""
    raise AssertionError("unreachable: contract_not_built already raised")
