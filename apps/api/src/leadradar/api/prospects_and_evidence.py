"""Router of the [Prospects and evidence](/architecture/interfaces.md#prospects-and-evidence)
family: `API-39`, `API-40`, `API-42` to `API-45`. `API-41` (score history) is built in
`leadradar.api.feedback_and_alerts`, which shares its `account_id`/`service_id` pair with
`API-46`. [`LeadFeedback`](/architecture/interfaces.md#leadfeedback) and
[`FindingView`](/architecture/interfaces.md#findingview) are defined there too, which `API-46`
and `API-47` need them for, and imported back here for `ScoreView.lead_feedback` and `API-42`, so
neither is defined twice. Each route validates its input, calls one `prospects` capability
function, and shapes the response (api Design "Layering")."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import CurrentUser, require_admin
from leadradar.api.feedback_and_alerts import FindingView, LeadFeedback, finding_view
from leadradar.api.outreach_and_crm import CrmSyncView
from leadradar.api.pagination import Page, PageRequest, page_request
from leadradar.core.enums import (
    AccountScoreBand,
    AccountScoreStanding,
    DisqualifierOverrideStatus,
    DocumentSourceType,
    FindingStatus,
    FindingStrength,
    SourcePluginCode,
)
from leadradar.core.score_breakdown import (
    DisqualifierBreakdown,
    FitBreakdown,
    QuestionBreakdown,
)
from leadradar.db.models.identity import AppUser
from leadradar.db.session import get_session
from leadradar.prospects.commands import create_override, revoke_override
from leadradar.prospects.queries import (
    ProspectFilters,
    list_findings,
    list_prospects,
    read_evidence,
    read_score_view,
)

ProspectSort = Literal["priority", "intent", "fit", "name", "last_refreshed"]

router = APIRouter(tags=["prospects-and-evidence"])


class ProspectAccount(BaseModel):
    """`ProspectRow.account`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    domain: str
    country_code: str | None
    industry: str | None


class ProspectTopSignal(BaseModel):
    """One entry of `ProspectRow.top_signals`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_key: str
    question_text: str
    strength: FindingStrength
    observed_at: str


class ProspectReason(BaseModel):
    """`ProspectRow.reason`: null when `RANKED`; the other members are null besides the one its
    standing names."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_fit: int | None
    disqualifier_labels: list[str] | None
    customer_marked_by_name: str | None


class ProspectRow(BaseModel):
    """[`ProspectRow`](/architecture/interfaces.md#prospectrow)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int | None
    account: ProspectAccount
    fit: int
    intent: int
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand | None
    reason: ProspectReason | None
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
    created_by_name: str
    created_at: str
    revoked_by_name: str | None
    revoked_at: str | None
    run_id: str | None


class OverrideCreate(BaseModel):
    """[`OverrideCreate`](/architecture/interfaces.md#overridecreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_key: str
    note: str


class ScoreViewQuestionBreakdown(QuestionBreakdown):
    """`ScoreView.breakdown`'s question entries, with `question_text` and the counted finding's
    `observed_at` added on read ([`ScoreView`](/architecture/interfaces.md#scoreview))."""

    question_text: str
    observed_at: datetime | None


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
    band: AccountScoreBand | None


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
    band: AccountScoreBand | None
    rank: int | None
    breakdown: ScoreViewBreakdown
    overrides: list[Override]
    lead_feedback: LeadFeedback | None
    last_crm_sync: CrmSyncView | None


class FindingDocument(BaseModel):
    """`FindingView.document`, reused by `EvidenceView.document` ("as in `FindingView`")."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str | None
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
async def get_prospects(
    id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
    paging: Annotated[PageRequest, Depends(page_request)],
    standing: AccountScoreStanding = AccountScoreStanding.RANKED,
    band: list[AccountScoreBand] | None = Query(default=None),
    country_code: list[str] | None = Query(default=None),
    industry: list[str] | None = Query(default=None),
    q: str | None = None,
    sort: ProspectSort | None = None,
) -> ProspectPage:
    """`API-39`."""
    page = await list_prospects(
        session,
        service_id=id,
        filters=ProspectFilters(
            standing=standing,
            bands=band,
            country_codes=country_code,
            industries=industry,
            q=q,
            sort=sort or "priority",
        ),
        page=paging.page,
        page_size=paging.page_size,
        top_signals=request.app.state.settings.prospect_top_signals,
    )
    return ProspectPage.model_validate(page)


@router.get("/accounts/{id}/scores/{service_id}", response_model=ScoreView)
async def get_score(
    id: uuid.UUID,
    service_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> ScoreView:
    """`API-40`: `404` when the account has no score for the service yet."""
    return ScoreView.model_validate(
        await read_score_view(session, account_id=id, service_id=service_id)
    )


@router.get("/accounts/{id}/findings", response_model=list[FindingView])
async def get_findings(
    id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
    service_id: uuid.UUID | None = None,
    question_id: uuid.UUID | None = None,
    status: FindingStatus = FindingStatus.ACTIVE,
) -> list[FindingView]:
    """`API-42`: ordered by contribution, then `observed_at` descending."""
    views = await list_findings(
        session, account_id=id, service_id=service_id, question_id=question_id, status=status
    )
    return [finding_view(view) for view in views]


@router.get("/findings/{id}/evidence", response_model=EvidenceView)
async def get_evidence(
    id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> EvidenceView:
    """`API-43`."""
    return EvidenceView.model_validate(
        await read_evidence(
            session,
            finding_id=id,
            context_chars=request.app.state.settings.evidence_context_chars,
        )
    )


@router.post("/accounts/{id}/scores/{service_id}/overrides", response_model=Override)
async def post_override(
    id: uuid.UUID,
    service_id: uuid.UUID,
    body: OverrideCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[AppUser, Depends(require_admin)],
) -> Override:
    """`API-44`: enqueues a `RESCORE` with trigger `OVERRIDE`."""
    return Override.model_validate(
        await create_override(
            session,
            account_id=id,
            service_id=service_id,
            rule_key=body.rule_key,
            note=body.note,
            principal=admin,
            now=request.app.state.clock(),
        )
    )


@router.post("/overrides/{id}/revoke", response_model=Override)
async def post_override_revoke(
    id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[AppUser, Depends(require_admin)],
) -> Override:
    """`API-45`: enqueues a `RESCORE` with trigger `OVERRIDE`."""
    return Override.model_validate(
        await revoke_override(
            session, override_id=id, principal=admin, now=request.app.state.clock()
        )
    )
