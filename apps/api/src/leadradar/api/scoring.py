"""Router for the [Scoring](/architecture/interfaces.md#scoring) interface family.

This module implements `API-18` only; `API-15`, `API-16`, `API-17`, `API-19` are deferred to
the service-configuration task.

`API-18` `POST /scoring-configs/{id}/activate` — Admin only; activates a DRAFT scoring config,
retires the previous ACTIVE version, creates a RESCORE run and returns `ScoringConfig`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import require_admin
from leadradar.api.errors import envelope
from leadradar.core.enums import ScoringConfigStatus
from leadradar.db.models.identity import AppUser
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
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
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

    try:
        result = await activate_scoring_config(
            session,
            config_id=config_id,
            actor_id=admin.id,
            change_note=body.change_note,
            request_id=request_id,
        )
    except ScoringConfigNotFound:
        return JSONResponse(
            status_code=404,
            content=envelope("NOT_FOUND", "Scoring config not found."),
        )
    except NotADraft as exc:
        return JSONResponse(
            status_code=409,
            content=envelope(
                "CONFLICT",
                f"Only a DRAFT config can be activated; current: {exc.status!r}.",
            ),
        )
    await session.commit()

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
