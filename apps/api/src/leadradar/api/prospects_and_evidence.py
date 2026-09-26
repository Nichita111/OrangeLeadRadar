"""Router of the [Prospects and evidence](/architecture/interfaces.md#prospects-and-evidence)
family: `API-39` to `API-45`. [`LeadFeedback`](/architecture/interfaces.md#leadfeedback) and
[`FindingView`](/architecture/interfaces.md#findingview) are defined by
[Feedback and alerts](/architecture/interfaces.md#feedback-and-alerts), which `API-46` and
`API-47` need them for, and imported back here for `ScoreView.lead_feedback` and `API-42`, so
neither is defined twice. Every route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel, ConfigDict

from leadradar.api.common import Page
from leadradar.api.feedback_and_alerts import FindingView, LeadFeedback
from leadradar.api.outreach_and_crm import CrmSyncView
from leadradar.api.router_utils import stub_router
from leadradar.core.enums import (
    AccountScoreBand,
    AccountScoreStanding,
    DisqualifierOverrideStatus,
    DocumentSourceType,
    FindingStatus,
    FindingStrength,
    PipelineRunTrigger,
    SourcePluginCode,
)
from leadradar.core.score_breakdown import (
    DisqualifierBreakdown,
    FitBreakdown,
    QuestionBreakdown,
)

ProspectSort = Literal["priority", "intent", "fit", "name", "last_refreshed"]

router = stub_router("prospects-and-evidence")


class ProspectAccount(BaseModel):
    """`ProspectRow.account`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    domain: str
    country_code: str
    industry: str | None


class ProspectTopSignal(BaseModel):
    """One entry of `ProspectRow.top_signals`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_key: str
    question_text: str
    strength: FindingStrength
    observed_at: str


class ProspectRow(BaseModel):
    """[`ProspectRow`](/architecture/interfaces.md#prospectrow)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int | None
    account: ProspectAccount
    fit: int
    intent: int
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand
    top_signals: list[ProspectTopSignal]
    finding_count: int
    unread_alerts: int
    as_of: str
    last_refreshed_at: str | None


class ProspectPage(Page[ProspectRow]):
    """[`ProspectPage`](/architecture/interfaces.md#prospectpage): `Page<ProspectRow>` plus
    `band_counts`."""

    band_counts: dict[AccountScoreBand, int]


class Override(BaseModel):
    """[`Override`](/architecture/interfaces.md#override)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    account_id: str
    service_id: str
    rule_key: str
    note: str
    rule_label: str
    status: DisqualifierOverrideStatus
    created_by_name: str | None
    created_at: str | None
    revoked_by_name: str | None
    revoked_at: str | None


class OverrideCreate(BaseModel):
    """[`OverrideCreate`](/architecture/interfaces.md#overridecreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_key: str
    note: str


class ScoreViewQuestionBreakdown(QuestionBreakdown):
    """`ScoreView.breakdown`'s question entries, with `question_text` added on read
    ([`ScoreView`](/architecture/interfaces.md#scoreview))."""

    question_text: str


class ScoreViewIntentBreakdown(BaseModel):
    """`ScoreView.breakdown.intent`, whose question entries carry `question_text`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: int
    positive_sum: float
    negative_sum: float
    max_positive: float
    questions: list[ScoreViewQuestionBreakdown]


class ScoreViewBreakdown(BaseModel):
    """`ScoreView.breakdown`: [Score breakdown](/architecture/rules.md#score-breakdown) with
    each question entry's `question_text` added."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    settings_version: int
    as_of: datetime
    fit: FitBreakdown
    intent: ScoreViewIntentBreakdown
    disqualifiers: list[DisqualifierBreakdown]
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand


class ScoreView(BaseModel):
    """[`ScoreView`](/architecture/interfaces.md#scoreview)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score_id: str
    account_id: str
    service_id: str
    scoring_version: int
    as_of: str
    fit: int
    intent: int
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand
    rank: int | None
    breakdown: ScoreViewBreakdown
    overrides: list[Override]
    lead_feedback: LeadFeedback | None
    last_crm_sync: CrmSyncView | None


class ScoreChangeFinding(BaseModel):
    """One entry of `ScoreChange.findings_added` and `.findings_removed`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str
    question_key: str


class ScoreChangeOverride(BaseModel):
    """One entry of `ScoreChange.overrides_changed`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_key: str
    overridden: bool


class ScoreChange(BaseModel):
    """[`ScoreChange`](/architecture/interfaces.md#scorechange)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score_id: str
    as_of: str
    fit: int
    intent: int
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand
    scoring_version: int
    trigger: PipelineRunTrigger
    run_id: str
    change_note: str | None
    findings_added: list[ScoreChangeFinding]
    findings_removed: list[ScoreChangeFinding]
    overrides_changed: list[ScoreChangeOverride]


class FindingDocument(BaseModel):
    """`FindingView.document`, reused by `EvidenceView.document`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    url: str
    source_type: DocumentSourceType
    plugin_code: SourcePluginCode
    language: str
    published_at: str | None


class EvidenceView(BaseModel):
    """[`EvidenceView`](/architecture/interfaces.md#evidenceview)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str
    document: FindingDocument
    section: str | None
    purged: bool
    excerpt: str | None
    quote_start: int | None
    quote_end: int | None


@router.get("/services/{id}/prospects", response_model=ProspectPage)
async def list_prospects(
    id: str,
    standing: AccountScoreStanding = AccountScoreStanding.RANKED,
    band: list[AccountScoreBand] | None = Query(default=None),
    country_code: list[str] | None = Query(default=None),
    industry: list[str] | None = Query(default=None),
    q: str | None = None,
    sort: ProspectSort | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> ProspectPage:
    """`API-39`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/accounts/{id}/scores/{service_id}", response_model=ScoreView)
async def get_score(id: str, service_id: str) -> ScoreView:
    """`API-40`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/accounts/{id}/scores/{service_id}/history", response_model=list[ScoreChange])
async def get_score_history(id: str, service_id: str) -> list[ScoreChange]:
    """`API-41`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/accounts/{id}/findings", response_model=list[FindingView])
async def list_findings(
    id: str,
    service_id: str | None = None,
    question_id: str | None = None,
    status: FindingStatus | None = None,
) -> list[FindingView]:
    """`API-42`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/findings/{id}/evidence", response_model=EvidenceView)
async def get_evidence(id: str) -> EvidenceView:
    """`API-43`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/accounts/{id}/scores/{service_id}/overrides", response_model=Override)
async def create_override(id: str, service_id: str, payload: OverrideCreate) -> Override:
    """`API-44`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/overrides/{id}/revoke", response_model=Override)
async def revoke_override(id: str) -> Override:
    """`API-45`."""
    raise AssertionError("unreachable: contract_not_built already raised")
