"""Router of the [Services and questions](/architecture/interfaces.md#services-and-questions)
family, its remaining route: `API-14`. `API-07` to `API-13` are built in
`leadradar.api.configuration`."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.ai.errors import BudgetExhausted, UpstreamUnavailable
from leadradar.ai.fixtures import FixtureMissing
from leadradar.api.authentication import require_admin
from leadradar.api.configuration import QuestionOption
from leadradar.api.errors import envelope
from leadradar.configuration.question_preview import PreviewRequest
from leadradar.configuration.question_preview import preview_question as run_preview
from leadradar.core.enums import (
    DocumentSourceType,
    DocumentTriageClassifier,
    FindingStrength,
    SignalQuestionAnswerType,
)
from leadradar.db.models.identity import AppUser
from leadradar.db.session import get_session

router = APIRouter(tags=["services-and-questions"])


class QuestionPreviewRequest(BaseModel):
    """[`QuestionPreviewRequest`](/architecture/interfaces.md#questionpreviewrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service_id: uuid.UUID
    question_id: uuid.UUID | SkipJsonSchema[None] = None
    text: str | SkipJsonSchema[None] = None
    answer_type: SignalQuestionAnswerType | SkipJsonSchema[None] = None
    options: list[QuestionOption] | SkipJsonSchema[None] = None
    source_types: list[DocumentSourceType] | SkipJsonSchema[None] = None
    hint_terms: list[str] | SkipJsonSchema[None] = None
    sample_text: str | SkipJsonSchema[None] = None
    account_id: uuid.UUID | SkipJsonSchema[None] = None


class QuestionPreviewDocument(BaseModel):
    """`QuestionPreview.results[].document`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    url: str
    published_at: str | None


class QuestionPreviewResult(BaseModel):
    """One entry of `QuestionPreview.results`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passage: str
    document: QuestionPreviewDocument | None
    p_positive: float
    escalated: bool
    strength: FindingStrength
    quote: str | None
    quote_en: str | None
    rationale: str | None


class QuestionPreview(BaseModel):
    """[`QuestionPreview`](/architecture/interfaces.md#questionpreview)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    classifier: DocumentTriageClassifier
    results: list[QuestionPreviewResult]


@router.post("/questions/preview", response_model=QuestionPreview)
async def preview_question(
    payload: QuestionPreviewRequest,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    """`API-14`: Admin only. `503 UPSTREAM_UNAVAILABLE` when the classifier, the LLM or the
    embedder fails, `429 BUDGET_EXHAUSTED` when the budget guard stops an LLM call."""
    state = request.app.state
    try:
        results = await run_preview(
            session,
            PreviewRequest(
                service_id=payload.service_id,
                question_id=payload.question_id,
                text=payload.text,
                answer_type=payload.answer_type,
                options=(
                    None
                    if payload.options is None
                    else [option.model_dump(mode="json") for option in payload.options]
                ),
                source_types=(
                    None
                    if payload.source_types is None
                    else [source_type.value for source_type in payload.source_types]
                ),
                hint_terms=payload.hint_terms,
                sample_text=payload.sample_text,
                account_id=payload.account_id,
            ),
            gateway=state.ai_gateway,
            embedder=state.embedder_client,
            settings=state.settings,
            max_passages=state.settings.preview_max_passages,
            actor_id=admin.id,
            now=state.clock(),
        )
    except BudgetExhausted as exc:
        return JSONResponse(
            status_code=429,
            content=envelope(
                "BUDGET_EXHAUSTED", str(exc), {"resets_at": exc.resets_at.isoformat()}
            ),
        )
    except UpstreamUnavailable as exc:
        return JSONResponse(
            status_code=503,
            content=envelope(
                "UPSTREAM_UNAVAILABLE",
                str(exc),
                {"dependency": exc.dependency.upper(), "reason": exc.reason},
            ),
        )
    except FixtureMissing as exc:
        return JSONResponse(
            status_code=503,
            content=envelope("UPSTREAM_UNAVAILABLE", str(exc), {"reason": "FIXTURE_MISSING"}),
        )
    response = QuestionPreview(
        classifier=state.ai_gateway.classifier,
        results=[
            QuestionPreviewResult(
                passage=result.passage,
                document=(
                    None
                    if result.url is None
                    else QuestionPreviewDocument(
                        title=result.title or result.url,
                        url=result.url,
                        published_at=(
                            None if result.published_at is None else result.published_at.isoformat()
                        ),
                    )
                ),
                p_positive=result.p_positive,
                escalated=result.escalated,
                strength=result.strength,
                quote=result.quote,
                quote_en=result.quote_en,
                rationale=result.rationale,
            )
            for result in results
        ],
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))
