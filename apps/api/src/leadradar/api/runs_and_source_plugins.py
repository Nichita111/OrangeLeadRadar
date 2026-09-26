"""Router of the [Runs and source plug-ins](/architecture/interfaces.md#runs-and-source-plug-ins)
family: `API-33` to `API-36`. The source plug-in contracts (`API-37`, `API-38`) join this router
with the task that builds them."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, ConfigDict, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import CurrentUser
from leadradar.api.pagination import Page, PageRequest, page_request
from leadradar.core.enums import (
    PipelineRunKind,
    PipelineRunStage,
    PipelineRunStatus,
    PipelineRunTrigger,
    SourcePluginCode,
)
from leadradar.db.session import get_session
from leadradar.runs.commands import cancel_run, request_account_refresh
from leadradar.runs.queries import RunFilters, RunView, get_run, get_runs_page
from leadradar.settings import ApiSettings

router = APIRouter(tags=["runs-and-source-plugins"])


class RunRef(BaseModel):
    """`Run.account` and `Run.service`: `{id, name}`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    name: str


class RunQuestion(BaseModel):
    """`Run.question`: `{id, key}`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    key: str


class RunError(BaseModel):
    """One entry of `Run.errors`, as [`pipeline_run`](/architecture/sql-store.md#pipeline_run)
    `errors` states it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: PipelineRunStage
    plugin_code: SourcePluginCode | None = None
    code: str
    message: str


class Run(BaseModel):
    """[`Run`](/architecture/interfaces.md#run)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    kind: PipelineRunKind
    trigger: PipelineRunTrigger
    status: PipelineRunStatus
    stage: PipelineRunStage | None
    progress: dict[str, int]
    errors: list[RunError]
    account: RunRef | None
    service: RunRef | None
    question: RunQuestion | None
    requested_by_name: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    ai_cost_eur: float


_PROGRESS = TypeAdapter(dict[str, int])


def _run(view: RunView) -> Run:
    return Run(
        id=view.id,
        kind=view.kind,
        trigger=view.trigger,
        status=view.status,
        stage=view.stage,
        progress=_PROGRESS.validate_python(view.progress),
        errors=[RunError.model_validate(entry) for entry in view.errors],
        account=RunRef(id=view.account.id, name=view.account.name) if view.account else None,
        service=RunRef(id=view.service.id, name=view.service.name) if view.service else None,
        question=(
            RunQuestion(id=view.question.id, key=view.question.key) if view.question else None
        ),
        requested_by_name=view.requested_by_name,
        created_at=view.created_at,
        started_at=view.started_at,
        finished_at=view.finished_at,
        ai_cost_eur=view.ai_cost_eur,
    )


def _plugins_with_a_key(settings: ApiSettings) -> frozenset[SourcePluginCode]:
    """The plug-ins whose key is set in the runtime; the keys themselves stay in `settings`."""
    keys = {
        SourcePluginCode.CRUNCHBASE: settings.crunchbase_api_key,
        SourcePluginCode.NEWSAPI: settings.newsapi_key,
        SourcePluginCode.SERPAPI: settings.serpapi_key,
    }
    return frozenset(code for code, key in keys.items() if key is not None)


@router.post(
    "/accounts/{id}/refresh",
    status_code=http_status.HTTP_202_ACCEPTED,
    responses={
        http_status.HTTP_200_OK: {"model": Run, "description": "The refresh already queued"}
    },
)
async def post_account_refresh(
    id: uuid.UUID,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> Run:
    """`API-33`: `202` with a new refresh, or `200` with the one already queued or running."""
    result = await request_account_refresh(
        session,
        account_id=id,
        principal=principal,
        keys_configured=_plugins_with_a_key(request.app.state.settings),
        now=request.app.state.clock(),
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return _run(result.run)


@router.get("/runs")
async def get_runs(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
    paging: Annotated[PageRequest, Depends(page_request)],
    kind: PipelineRunKind | None = None,
    status: PipelineRunStatus | None = None,
    account_id: uuid.UUID | None = None,
    service_id: uuid.UUID | None = None,
) -> Page[Run]:
    """`API-34`: runs newest first, filtered by kind, status, account and service."""
    views, total = await get_runs_page(
        session,
        RunFilters(kind=kind, status=status, account_id=account_id, service_id=service_id),
        page=paging.page,
        page_size=paging.page_size,
    )
    return Page[Run](
        items=[_run(view) for view in views],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


@router.get("/runs/{id}")
async def get_run_by_id(
    id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> Run:
    """`API-35`: one run with its stage, progress and errors."""
    return _run(await get_run(session, id))


@router.post("/runs/{id}/cancel")
async def post_run_cancel(
    id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> Run:
    """`API-36`: cancels a queued or running run; Admin only for `RECLASSIFY`, `RESCORE` and
    `EVALUATION` runs."""
    return _run(
        await cancel_run(session, run_id=id, principal=principal, now=request.app.state.clock())
    )
