"""Router of the [Runs and source plug-ins](/architecture/interfaces.md#runs-and-source-plug-ins)
family: `API-33` to `API-38`. Every route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from leadradar.api.common import IdName, Page
from leadradar.api.router_utils import stub_router
from leadradar.core.enums import (
    PipelineRunKind,
    PipelineRunStage,
    PipelineRunStatus,
    PipelineRunTrigger,
    SourcePluginCode,
)

router = stub_router("runs-and-source-plugins")


class RunQuestion(BaseModel):
    """`Run.question`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    key: str


class Run(BaseModel):
    """[`Run`](/architecture/interfaces.md#run)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: PipelineRunKind
    trigger: PipelineRunTrigger
    status: PipelineRunStatus
    stage: PipelineRunStage | None
    progress: dict[str, object]
    errors: list[dict[str, object]]
    account: IdName | None
    service: IdName | None
    question: RunQuestion | None
    requested_by_name: str | None
    created_at: str | None
    started_at: str | None
    finished_at: str | None
    ai_cost_eur: float


class SourcePlugin(BaseModel):
    """[`SourcePlugin`](/architecture/interfaces.md#sourceplugin)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: SourcePluginCode
    enabled: bool
    rate_limit_per_minute: int
    daily_quota: int
    needs_key: bool
    key_configured: bool
    available: bool
    requests_today: int
    last_success_at: str | None
    last_error: str | None
    last_error_at: str | None


class SourcePluginUpdate(BaseModel):
    """[`SourcePluginUpdate`](/architecture/interfaces.md#sourcepluginupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool | None = None
    rate_limit_per_minute: int | None = None
    daily_quota: int | None = None


@router.post(
    "/accounts/{id}/refresh",
    response_model=Run,
    status_code=202,
    responses={200: {"model": Run}},
)
async def refresh_account(id: str) -> Run:
    """`API-33`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/runs", response_model=Page[Run])
async def list_runs(
    kind: PipelineRunKind | None = None,
    status: PipelineRunStatus | None = None,
    account_id: str | None = None,
    service_id: str | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> Page[Run]:
    """`API-34`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/runs/{id}", response_model=Run)
async def get_run(id: str) -> Run:
    """`API-35`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/runs/{id}/cancel", response_model=Run)
async def cancel_run(id: str) -> Run:
    """`API-36`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/source-plugins", response_model=list[SourcePlugin])
async def list_source_plugins() -> list[SourcePlugin]:
    """`API-37`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/source-plugins/{code}", response_model=SourcePlugin)
async def update_source_plugin(code: str, payload: SourcePluginUpdate) -> SourcePlugin:
    """`API-38`."""
    raise AssertionError("unreachable: contract_not_built already raised")
