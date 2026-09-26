"""Router of the [Scoring](/architecture/interfaces.md#scoring) family: `API-15` to `API-19`.
Every route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from leadradar.api.router_utils import stub_router
from leadradar.core.enums import AccountScoreBand, AccountScoreStanding, ScoringConfigStatus
from leadradar.core.scoring_settings import ScoringSettingsDocument

router = stub_router("scoring")


class ScoringConfigSummary(BaseModel):
    """[`ScoringConfigSummary`](/architecture/interfaces.md#scoringconfigsummary)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    service_id: str
    version: int
    status: ScoringConfigStatus
    change_note: str | None
    activated_at: str | None
    activated_by_name: str | None


class ScoringConfig(ScoringConfigSummary):
    """[`ScoringConfig`](/architecture/interfaces.md#scoringconfig): every field of
    [`ScoringConfigSummary`](#scoringconfigsummary) plus `settings`."""

    settings: ScoringSettingsDocument


class ScoringDraftUpdate(BaseModel):
    """[`ScoringDraftUpdate`](/architecture/interfaces.md#scoringdraftupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    settings: ScoringSettingsDocument
    change_note: str | None = None


class ActivationRequest(BaseModel):
    """[`ActivationRequest`](/architecture/interfaces.md#activationrequest)."""

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
    band: AccountScoreBand
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


@router.get("/services/{id}/scoring-configs", response_model=list[ScoringConfigSummary])
async def list_scoring_configs(id: str) -> list[ScoringConfigSummary]:
    """`API-15`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/scoring-configs/{id}", response_model=ScoringConfig)
async def get_scoring_config(id: str) -> ScoringConfig:
    """`API-16`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.put("/services/{id}/scoring-configs/draft", response_model=ScoringConfig)
async def update_scoring_draft(id: str, payload: ScoringDraftUpdate) -> ScoringConfig:
    """`API-17`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/scoring-configs/{id}/activate", response_model=ScoringConfig)
async def activate_scoring_config(id: str, payload: ActivationRequest) -> ScoringConfig:
    """`API-18`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/scoring-configs/{id}/preview", response_model=ScoringPreview)
async def preview_scoring_config(id: str) -> ScoringPreview:
    """`API-19`."""
    raise AssertionError("unreachable: contract_not_built already raised")
