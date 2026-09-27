"""Router for the [Scoring](/architecture/interfaces.md#scoring) interface family.

`API-15` to `API-17` are built in `leadradar.api.configuration`. This module implements `API-18`
and `API-19`.

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
from leadradar.api.configuration import ScoringConfig
from leadradar.api.errors import envelope
from leadradar.core.enums import AccountScoreBand, AccountScoreStanding
from leadradar.db.models.identity import AppUser
from leadradar.db.session import get_session
from leadradar.scoring.activate import activate_scoring_config
from leadradar.scoring.errors import NoActiveVersion, NotADraft, ScoringConfigNotFound
from leadradar.scoring.preview import PreviewScore, preview_scoring_config

router = APIRouter(tags=["scoring"])


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------


class ActivationRequest(BaseModel):
    """[`ActivationRequest`](/architecture/interfaces.md#activationrequest): `change_note`
    required."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    change_note: str


class ScoringPreviewAccount(BaseModel):
    """`ScoringPreview.changes[].account`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str


class ScoringPreviewScore(BaseModel):
    """`ScoringPreview.changes[].current` and `.proposed`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand | None
    rank: int | None


class ScoringPreviewChange(BaseModel):
    """One entry of `ScoringPreview.changes`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    account: ScoringPreviewAccount
    current: ScoringPreviewScore
    proposed: ScoringPreviewScore


class ScoringPreview(BaseModel):
    """[`ScoringPreview`](/architecture/interfaces.md#scoringpreview)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draft_version: int
    active_version: int
    changes: list[ScoringPreviewChange]
    unchanged_count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/scoring-configs/{id}/activate",
    response_model=ScoringConfig,
    summary="API-18: Activate a DRAFT scoring config",
)
async def activate_scoring_config_route(
    id: uuid.UUID,
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
    try:
        result = await activate_scoring_config(
            session,
            config_id=id,
            actor_id=admin.id,
            change_note=body.change_note,
            now=request.app.state.clock(),
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
        activated_by_name=admin.display_name,
        settings=result.settings,
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@router.post(
    "/scoring-configs/{id}/preview",
    response_model=ScoringPreview,
    summary="API-19: Preview the impact of a DRAFT scoring config",
)
async def preview_scoring_config_route(
    id: uuid.UUID,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    """[`API-19`](/architecture/interfaces.md#scoring): Admin only. Computes, without writing,
    every current score of the draft's service under the draft. `404` for an unknown config,
    `409 CONFLICT` when it is not a DRAFT or its service has no ACTIVE version."""
    try:
        result = await preview_scoring_config(session, config_id=id)
    except ScoringConfigNotFound:
        return JSONResponse(
            status_code=404, content=envelope("NOT_FOUND", "Scoring config not found.")
        )
    except NotADraft as exc:
        return JSONResponse(
            status_code=409,
            content=envelope(
                "CONFLICT", f"Only a DRAFT config can be previewed; current: {exc.status!r}."
            ),
        )
    except NoActiveVersion:
        return JSONResponse(
            status_code=409,
            content=envelope("CONFLICT", "The service has no active scoring version to compare."),
        )

    def shape(score: PreviewScore) -> ScoringPreviewScore:
        return ScoringPreviewScore(
            priority=score.priority, standing=score.standing, band=score.band, rank=score.rank
        )

    response = ScoringPreview(
        draft_version=result.draft_version,
        active_version=result.active_version,
        changes=[
            ScoringPreviewChange(
                account=ScoringPreviewAccount(id=str(change.account_id), name=change.account_name),
                current=shape(change.current),
                proposed=shape(change.proposed),
            )
            for change in result.changes
        ],
        unchanged_count=result.unchanged_count,
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))
