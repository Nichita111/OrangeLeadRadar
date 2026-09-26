"""Router for the [Scoring](/architecture/interfaces.md#scoring) interface family.

This module implements `API-18` only; `API-15`, `API-16`, `API-17`, `API-19` are deferred to
the service-configuration task.

`API-18` `POST /scoring-configs/{id}/activate` — Admin only; activates a DRAFT scoring config,
retires the previous ACTIVE version, creates a RESCORE run and returns `ScoringConfig`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from leadradar.api.errors import envelope
from leadradar.core.enums import ScoringConfigStatus
from leadradar.db.session import get_session
from leadradar.scoring.activate import activate_scoring_config
from leadradar.scoring.errors import NotADraft, ScoringConfigNotFound

router = APIRouter(tags=["scoring"])


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------


class ActivationRequest(BaseModel):
    """`ActivationRequest`: `change_note` required."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    change_note: str


class ScoringConfig(BaseModel):
    """`ScoringConfig` ([interfaces](/architecture/interfaces.md#scoringconfig))."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    service_id: str
    version: int
    status: ScoringConfigStatus
    change_note: str | None
    activated_at: str | None
    activated_by_name: str | None
    settings: dict[str, object]


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def _require_admin(request: Request) -> uuid.UUID:
    """Dependency: require an authenticated Admin user.

    Authentication and session are out of scope for this task; this dependency
    reads the `X-Actor-Id` and `X-Actor-Role` headers that the auth middleware
    will eventually inject, so the contract tests can stub them.

    Returns the actor's UUID; raises `401` / `403` for missing auth or wrong role.
    """
    actor_id_hdr = request.headers.get("X-Actor-Id")
    actor_role_hdr = request.headers.get("X-Actor-Role", "")

    if not actor_id_hdr:
        raise HTTPException(
            status_code=401,
            detail=envelope("UNAUTHENTICATED", "Authentication required."),
        )
    if actor_role_hdr.upper() != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail=envelope("FORBIDDEN", "Admin role required."),
        )
    try:
        return uuid.UUID(actor_id_hdr)
    except ValueError as err:
        raise HTTPException(
            status_code=403,
            detail=envelope("FORBIDDEN", "Invalid actor id."),
        ) from err


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/scoring-configs/{config_id}/activate",
    summary="API-18: Activate a DRAFT scoring config",
)
async def activate_scoring_config_route(
    config_id: uuid.UUID,
    body: ActivationRequest,
    request: Request,
    actor_id: uuid.UUID = Depends(_require_admin),
) -> JSONResponse:
    """[`API-18`](/architecture/interfaces.md#scoring): Admin only.

    Activates the target DRAFT scoring config, retires the previous ACTIVE version, and
    enqueues a RESCORE run. Returns the activated `ScoringConfig`.
    `409 CONFLICT` when the config is not DRAFT. `422` when `change_note` is missing.
    `403 FORBIDDEN` for non-Admin.
    """
    request_id: str | None = (
        request.state.request_id if hasattr(request.state, "request_id") else None
    )

    async with get_session(request.app.state.engine) as session, session.begin():
        try:
            result = await activate_scoring_config(
                session,
                config_id=config_id,
                actor_id=actor_id,
                change_note=body.change_note,
                request_id=request_id,
            )
        except ScoringConfigNotFound:
            return JSONResponse(
                status_code=404,
                content=envelope("NOT_FOUND", "Scoring config not found."),
            )
        except NotADraft as exc:
            status_msg = exc.status
            return JSONResponse(
                status_code=409,
                content=envelope(
                    "CONFLICT",
                    f"Only a DRAFT config can be activated; current: {status_msg!r}.",
                ),
            )

    activated_at_str: str | None = None
    if result.activated_at is not None:
        dt: datetime = result.activated_at
        if dt.tzinfo is None:
            activated_at_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            activated_at_str = dt.isoformat()

    response = ScoringConfig(
        id=str(result.id),
        service_id=str(result.service_id),
        version=result.version,
        status=result.status,
        change_note=result.change_note,
        activated_at=activated_at_str,
        # display_name lookup deferred to service-configuration task
        activated_by_name=None,
        settings=result.settings,
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))
