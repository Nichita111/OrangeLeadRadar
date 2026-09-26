"""Router of the [Outreach and CRM](/architecture/interfaces.md#outreach-and-crm) family. Only
`API-59` is in scope of this task; `API-56` to `API-58` are `S-OUT-01`'s."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import CurrentUser
from leadradar.clock import now
from leadradar.core.enums import CrmSyncStatus, CrmSyncTarget
from leadradar.db.session import get_session
from leadradar.logs import request_id_var
from leadradar.outreach.commands import push_to_crm

router = APIRouter(tags=["outreach-and-crm"])


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
    current_time = now(fixture_mode=settings.fixture_mode, clock_file=settings.clock_file)
    result = await push_to_crm(
        session,
        account_id=id,
        service_id=service_id,
        principal=principal,
        settings=settings,
        http=request.app.state.http_client,
        now=current_time,
        request_id=request_id_var.get(),
    )
    return CrmSyncView(
        id=result.id,
        external_id=result.external_id,
        error=result.error,
        created_at=result.created_at,
        target=result.target,
        status=result.status,
    )
