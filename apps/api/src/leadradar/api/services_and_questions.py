"""Router of the [Services and questions](/architecture/interfaces.md#services-and-questions)
family, its remaining route: `API-14`. `API-07` to `API-13` are built in
`leadradar.api.configuration`. A declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema

from leadradar.api.configuration import QuestionOption
from leadradar.api.router_utils import stub_router
from leadradar.core.enums import (
    DocumentSourceType,
    DocumentTriageClassifier,
    FindingStrength,
    SignalQuestionAnswerType,
)

router = stub_router("services-and-questions")


class QuestionPreviewRequest(BaseModel):
    """[`QuestionPreviewRequest`](/architecture/interfaces.md#questionpreviewrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service_id: str
    question_id: str | SkipJsonSchema[None] = None
    text: str | SkipJsonSchema[None] = None
    answer_type: SignalQuestionAnswerType | SkipJsonSchema[None] = None
    options: list[QuestionOption] | SkipJsonSchema[None] = None
    source_types: list[DocumentSourceType] | SkipJsonSchema[None] = None
    hint_terms: list[str] | SkipJsonSchema[None] = None
    sample_text: str | SkipJsonSchema[None] = None
    account_id: str | SkipJsonSchema[None] = None


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
async def preview_question(payload: QuestionPreviewRequest) -> QuestionPreview:
    """`API-14`."""
    raise AssertionError("unreachable: contract_not_built already raised")
