"""Router of the [Audit and health](/architecture/interfaces.md#audit-and-health) family.
Only `API-61` `GET /health` is in scope of this task; `API-60` `GET /audit` needs sessions and
roles, out of scope here."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from leadradar.audit.health import HealthCheckStatus, HealthStatus, read_health

router = APIRouter(tags=["audit-and-health"])


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
