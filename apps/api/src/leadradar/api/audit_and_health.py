"""Router of the [Audit and health](/architecture/interfaces.md#audit-and-health) family.
`API-61` `GET /health` is anonymous and built; `API-60` `GET /audit` is a declared stub
answering `501 NOT_IMPLEMENTED` until Admin sessions and roles exist."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from leadradar.api.common import Page
from leadradar.api.errors import ErrorEnvelope
from leadradar.api.not_built import contract_not_built
from leadradar.audit.health import HealthCheckStatus, HealthStatus, read_health
from leadradar.core.enums import AuditEventKind

router = APIRouter(tags=["audit-and-health"])
audit_stub_router = APIRouter(
    tags=["audit-and-health"],
    dependencies=[Depends(contract_not_built)],
    responses={422: {"model": ErrorEnvelope}, 501: {"model": ErrorEnvelope}},
)


class AuditEntry(BaseModel):
    """[`AuditEntry`](/architecture/interfaces.md#auditentry)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    occurred_at: str
    entity_type: str | None
    entity_id: str | None
    run_id: str | None
    request_id: str | None
    payload: dict[str, object]
    kind: AuditEventKind
    action: str
    actor_name: str | None


@audit_stub_router.get("/audit", response_model=Page[AuditEntry])
async def list_audit_entries(
    kind: list[AuditEventKind] | None = Query(default=None),
    action: str | None = None,
    actor_id: str | None = None,
    entity_id: str | None = None,
    run_id: str | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> Page[AuditEntry]:
    """`API-60`."""
    raise AssertionError("unreachable: contract_not_built already raised")


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
