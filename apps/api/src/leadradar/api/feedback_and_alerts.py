"""Router of the [Feedback and alerts](/architecture/interfaces.md#feedback-and-alerts) family:
`API-46` to `API-49`. `API-41` ([Prospects and evidence]
(/architecture/interfaces.md#prospects-and-evidence)'s score history) is added alongside them,
since it reads the same `account_id`/`service_id` pair as `API-46` and shares this router with
the Alerts screen it is read from ([History tab](/features/prospect-dashboard.md#account-detail),
[Alerts](/features/prospect-dashboard.md#alerts): `S-PRO-04`, `S-PRO-06`)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.alerts.commands import acknowledge_alert
from leadradar.alerts.queries import AlertFilters, AlertRow, list_alerts
from leadradar.api.authentication import CurrentUser
from leadradar.api.pagination import Page, PageRequest, page_request
from leadradar.core.enums import (
    AccountScoreBand,
    AccountScoreStanding,
    AlertKind,
    DocumentSourceType,
    FindingDecidedBy,
    FindingFeedbackVerdict,
    FindingStatus,
    FindingStrength,
    LeadFeedbackVerdict,
    PipelineRunTrigger,
    SignalQuestionPolarity,
    SourcePluginCode,
)
from leadradar.db.session import get_session
from leadradar.feedback.commands import give_finding_feedback, give_lead_feedback
from leadradar.feedback.queries import read_score_history

router = APIRouter(tags=["feedback-and-alerts"])


class FeedbackCreate[VerdictT: (LeadFeedbackVerdict, FindingFeedbackVerdict)](BaseModel):
    """[`FeedbackCreate`](/architecture/interfaces.md#feedbackcreate), the request of `API-46`
    and `API-47`, parametrised by the verdict enum of the table it targets: a verdict of the
    other table's enum is refused by validation, naming `verdict`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: VerdictT
    note: str | None = None


class LeadFeedback(BaseModel):
    """[`LeadFeedback`](/architecture/interfaces.md#leadfeedback), the response of `API-46`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    verdict: LeadFeedbackVerdict
    note: str | None
    created_at: datetime
    user_name: str


class FindingViewQuestion(BaseModel):
    """`FindingView.question`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    key: str
    text: str
    polarity: SignalQuestionPolarity


class FindingViewOption(BaseModel):
    """`FindingView.option`; `CHOICE` questions only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str


class FindingViewDocument(BaseModel):
    """`FindingView.document`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    title: str | None
    url: str
    source_type: DocumentSourceType
    plugin_code: SourcePluginCode
    language: str
    published_at: datetime | None


class FindingViewFeedback(BaseModel):
    """`FindingView.feedback`: the in-force [`finding_feedback`]
    (/architecture/sql-store.md#finding_feedback)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: FindingFeedbackVerdict
    user_name: str
    created_at: datetime


class FindingView(BaseModel):
    """[`FindingView`](/architecture/interfaces.md#findingview), the response of `API-47`. Also
    plan task 13's `API-42` response shape; that task imports this model and must not define a
    second one."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    account_id: uuid.UUID
    service_id: uuid.UUID
    question: FindingViewQuestion
    question_revision: int
    confidence: float
    quote: str
    quote_en: str | None
    rationale: str
    observed_at: datetime
    strength: FindingStrength
    decided_by: FindingDecidedBy
    status: FindingStatus
    option: FindingViewOption | None
    document: FindingViewDocument
    points: float | None
    feedback: FindingViewFeedback | None


@router.post("/accounts/{id}/scores/{service_id}/feedback")
async def post_lead_feedback(
    id: uuid.UUID,
    service_id: uuid.UUID,
    body: FeedbackCreate[LeadFeedbackVerdict],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> LeadFeedback:
    """`API-46`: applies the api's half of [Feedback effects]
    (/architecture/rules.md#feedback-effects) to the account's lead."""
    current_time = request.app.state.clock()
    result = await give_lead_feedback(
        session,
        account_id=id,
        service_id=service_id,
        verdict=body.verdict,
        note=body.note,
        principal=principal,
        now=current_time,
    )
    return LeadFeedback(
        id=result.id,
        verdict=result.verdict,
        note=result.note,
        created_at=result.created_at,
        user_name=result.user_name,
    )


@router.post("/findings/{id}/feedback")
async def post_finding_feedback(
    id: uuid.UUID,
    body: FeedbackCreate[FindingFeedbackVerdict],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> FindingView:
    """`API-47`: applies the api's half of [Feedback effects]
    (/architecture/rules.md#feedback-effects) to one finding."""
    current_time = request.app.state.clock()
    view = await give_finding_feedback(
        session,
        finding_id=id,
        verdict=body.verdict,
        note=body.note,
        principal=principal,
        now=current_time,
    )
    return FindingView(
        id=view.id,
        account_id=view.account_id,
        service_id=view.service_id,
        question=FindingViewQuestion(
            id=view.question.id,
            key=view.question.key,
            text=view.question.text,
            polarity=view.question.polarity,
        ),
        question_revision=view.question_revision,
        confidence=view.confidence,
        quote=view.quote,
        quote_en=view.quote_en,
        rationale=view.rationale,
        observed_at=view.observed_at,
        strength=view.strength,
        decided_by=view.decided_by,
        status=view.status,
        option=(
            FindingViewOption(key=view.option.key, label=view.option.label)
            if view.option is not None
            else None
        ),
        document=FindingViewDocument(
            id=view.document.id,
            title=view.document.title,
            url=view.document.url,
            source_type=view.document.source_type,
            plugin_code=view.document.plugin_code,
            language=view.document.language,
            published_at=view.document.published_at,
        ),
        points=view.points,
        feedback=(
            FindingViewFeedback(
                verdict=view.feedback.verdict,
                user_name=view.feedback.user_name,
                created_at=view.feedback.created_at,
            )
            if view.feedback is not None
            else None
        ),
    )


class ScoreChangeFinding(BaseModel):
    """One entry of `ScoreChange.findings_added` or `findings_removed`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: uuid.UUID
    question_key: str


class ScoreChangeOverride(BaseModel):
    """One entry of `ScoreChange.overrides_changed`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_key: str
    overridden: bool


class ScoreChange(BaseModel):
    """[`ScoreChange`](/architecture/interfaces.md#scorechange), one item of `API-41`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score_id: uuid.UUID
    as_of: datetime
    fit: int
    intent: int
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand | None
    scoring_version: int
    trigger: PipelineRunTrigger
    run_id: uuid.UUID
    change_note: str | None
    findings_added: list[ScoreChangeFinding]
    findings_removed: list[ScoreChangeFinding]
    overrides_changed: list[ScoreChangeOverride]


@router.get("/accounts/{id}/scores/{service_id}/history")
async def get_score_history(
    id: uuid.UUID,
    service_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> list[ScoreChange]:
    """`API-41`: the account and service's score history, newest first, each entry compared with
    the row before it. An account with no score for the service yet answers an empty list."""
    changes = await read_score_history(session, account_id=id, service_id=service_id)
    return [
        ScoreChange(
            score_id=change.score_id,
            as_of=change.as_of,
            fit=change.fit,
            intent=change.intent,
            priority=change.priority,
            standing=change.standing,
            band=change.band,
            scoring_version=change.scoring_version,
            trigger=change.trigger,
            run_id=change.run_id,
            change_note=change.change_note,
            findings_added=[
                ScoreChangeFinding(finding_id=entry.finding_id, question_key=entry.question_key)
                for entry in change.findings_added
            ],
            findings_removed=[
                ScoreChangeFinding(finding_id=entry.finding_id, question_key=entry.question_key)
                for entry in change.findings_removed
            ],
            overrides_changed=[
                ScoreChangeOverride(rule_key=entry.rule_key, overridden=entry.overridden)
                for entry in change.overrides_changed
            ],
        )
        for change in changes
    ]


class AlertRef(BaseModel):
    """`AlertView.account` and `AlertView.service`: `{id, name}`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    name: str


class AlertFinding(BaseModel):
    """`AlertView.finding`; `STRONG_SIGNAL` only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    question_text: str
    strength: FindingStrength
    quote: str


class AlertBandChange(BaseModel):
    """`AlertView.band_change`; `BAND_UP` only."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    from_band: AccountScoreBand | None = Field(alias="from")
    to: AccountScoreBand | None


class AlertView(BaseModel):
    """[`AlertView`](/architecture/interfaces.md#alertview), the response of `API-48` and
    `API-49`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    created_at: datetime
    acknowledged_at: datetime | None
    kind: AlertKind
    account: AlertRef
    service: AlertRef
    finding: AlertFinding | None
    band_change: AlertBandChange | None
    acknowledged_by_name: str | None


def _alert_view(row: AlertRow) -> AlertView:
    return AlertView(
        id=row.id,
        created_at=row.created_at,
        acknowledged_at=row.acknowledged_at,
        kind=row.kind,
        account=AlertRef(id=row.account.id, name=row.account.name),
        service=AlertRef(id=row.service.id, name=row.service.name),
        finding=(
            AlertFinding(
                id=row.finding.id,
                question_text=row.finding.question_text,
                strength=row.finding.strength,
                quote=row.finding.quote,
            )
            if row.finding is not None
            else None
        ),
        band_change=(
            AlertBandChange(from_band=row.band_change.from_band, to=row.band_change.to_band)
            if row.band_change is not None
            else None
        ),
        acknowledged_by_name=row.acknowledged_by_name,
    )


@router.get("/alerts")
async def get_alerts(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
    paging: Annotated[PageRequest, Depends(page_request)],
    service_id: uuid.UUID | None = None,
    unread: bool | None = None,
) -> Page[AlertView]:
    """`API-48`: newest first; `unread` true lists unacknowledged alerts only."""
    rows, total = await list_alerts(
        session,
        AlertFilters(service_id=service_id, unread=unread),
        page=paging.page,
        page_size=paging.page_size,
    )
    return Page[AlertView](
        items=[_alert_view(row) for row in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


@router.post("/alerts/{id}/acknowledge")
async def post_alert_acknowledge(
    id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> AlertView:
    """`API-49`: acknowledging an already acknowledged alert returns it unchanged."""
    result = await acknowledge_alert(
        session, alert_id=id, principal=principal, now=request.app.state.clock()
    )
    return _alert_view(result)
