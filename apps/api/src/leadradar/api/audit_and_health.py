"""Router of the [Audit and health](/architecture/interfaces.md#audit-and-health) family:
`API-60` `GET /audit` and `API-61` `GET /health`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import require_admin
from leadradar.api.pagination import Page, PageRequest, page_request
from leadradar.audit.health import HealthCheckStatus, HealthStatus, read_health
from leadradar.audit.queries import AuditEntryView, AuditFilters, get_audit_page
from leadradar.core.enums import AuditAction, AuditEventKind
from leadradar.db.models.identity import AppUser
from leadradar.db.session import get_session

router = APIRouter(tags=["audit-and-health"])


class AuditEntry(BaseModel):
    """[`AuditEntry`](/architecture/interfaces.md#auditentry), one item of `API-60`'s page."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    occurred_at: datetime
    kind: AuditEventKind
    action: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    run_id: uuid.UUID | None
    request_id: str | None
    payload: dict[str, object]
    actor_name: str | None


def _audit_entry(view: AuditEntryView) -> AuditEntry:
    return AuditEntry(
        id=view.id,
        occurred_at=view.occurred_at,
        kind=view.kind,
        action=view.action,
        entity_type=view.entity_type,
        entity_id=view.entity_id,
        run_id=view.run_id,
        request_id=view.request_id,
        payload=view.payload,
        actor_name=view.actor_name,
    )


@router.get("/audit")
async def get_audit(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    _admin: Annotated[AppUser, Depends(require_admin)],
    paging: Annotated[PageRequest, Depends(page_request)],
    kind: Annotated[list[AuditEventKind] | None, Query()] = None,
    action: AuditAction | None = None,
    actor_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> Page[AuditEntry]:
    """`API-60`: newest first, filtered by kind, action, user, entity, run and date range;
    without `from` the range is the last `AUDIT_DEFAULT_RANGE_DAYS` days."""
    settings = request.app.state.settings
    views, total = await get_audit_page(
        session,
        settings,
        AuditFilters(
            kind=kind,
            action=action,
            actor_id=actor_id,
            entity_id=entity_id,
            run_id=run_id,
            occurred_from=from_,
            occurred_to=to,
        ),
        page=paging.page,
        page_size=paging.page_size,
        now=request.app.state.clock(),
    )
    return Page[AuditEntry](
        items=[_audit_entry(view) for view in views],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


class HealthChecks(BaseModel):
    """The `checks` object of [Health](/architecture/interfaces.md#health)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    database: HealthCheckStatus
    embedder: HealthCheckStatus
    classifier: HealthCheckStatus
    llm: HealthCheckStatus


class Health(BaseModel):
    """[Health](/architecture/interfaces.md#health), the response of `API-61`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: HealthStatus
    checks: HealthChecks


@router.get("/health", responses={200: {"model": Health}, 503: {"model": Health}})
async def get_health(request: Request) -> JSONResponse:
    """`API-61`: anonymous, `200` when the database check is `OK`, else `503`."""
    result = await read_health(
        request.app.state.settings, request.app.state.engine, request.app.state.http_client
    )
    health = Health(status=result.status, checks=HealthChecks(**result.checks))
    status_code = 200 if result.checks["database"] == HealthCheckStatus.OK else 503
    return JSONResponse(status_code=status_code, content=health.model_dump(mode="json"))
