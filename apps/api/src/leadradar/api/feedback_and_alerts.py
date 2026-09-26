"""Router of the [Feedback and alerts](/architecture/interfaces.md#feedback-and-alerts) family.
Only `API-46` and `API-47` are in scope of this task; `API-48` and `API-49` are plan task 19's."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import CurrentUser
from leadradar.core.enums import (
    DocumentSourceType,
    FindingDecidedBy,
    FindingFeedbackVerdict,
    FindingStatus,
    FindingStrength,
    LeadFeedbackVerdict,
    SignalQuestionPolarity,
    SourcePluginCode,
)
from leadradar.db.session import get_session
from leadradar.feedback.commands import give_finding_feedback, give_lead_feedback

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
