"""Router of the [Services and questions](/architecture/interfaces.md#services-and-questions)
family: `API-07` to `API-14`. Every route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from leadradar.api.router_utils import stub_router
from leadradar.core.enums import (
    DocumentSourceType,
    DocumentTriageClassifier,
    FindingStrength,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
)

router = stub_router("services-and-questions")


class QuestionOption(BaseModel):
    """One entry of `SignalQuestion.options`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    strength: FindingStrength


class Service(BaseModel):
    """[`Service`](/architecture/interfaces.md#service)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    code: str
    name: str
    description: str
    value_proposition: str
    status: ServiceStatus
    active_version: int | None
    draft_version: int | None
    question_count: int


class ServiceCreate(BaseModel):
    """[`ServiceCreate`](/architecture/interfaces.md#servicecreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    name: str
    description: str
    value_proposition: str


class ServiceUpdate(BaseModel):
    """[`ServiceUpdate`](/architecture/interfaces.md#serviceupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = None
    description: str | None = None
    value_proposition: str | None = None
    status: ServiceStatus | None = None


class SignalQuestion(BaseModel):
    """[`SignalQuestion`](/architecture/interfaces.md#signalquestion)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    service_id: str
    key: str
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[QuestionOption] | None
    polarity: SignalQuestionPolarity
    source_types: list[DocumentSourceType]
    hint_terms: list[str]
    revision: int
    status: SignalQuestionStatus
    finding_count: int


class SignalQuestionCreate(BaseModel):
    """[`SignalQuestionCreate`](/architecture/interfaces.md#signalquestioncreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[QuestionOption] | None = None
    polarity: SignalQuestionPolarity
    source_types: list[DocumentSourceType]
    hint_terms: list[str] | None = None


class SignalQuestionUpdate(BaseModel):
    """[`SignalQuestionUpdate`](/architecture/interfaces.md#signalquestionupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str | None = None
    answer_type: SignalQuestionAnswerType | None = None
    options: list[QuestionOption] | None = None
    source_types: list[DocumentSourceType] | None = None
    hint_terms: list[str] | None = None
    status: SignalQuestionStatus | None = None


class QuestionPreviewRequest(BaseModel):
    """[`QuestionPreviewRequest`](/architecture/interfaces.md#questionpreviewrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service_id: str
    question_id: str | None = None
    text: str | None = None
    answer_type: SignalQuestionAnswerType | None = None
    options: list[QuestionOption] | None = None
    source_types: list[DocumentSourceType] | None = None
    hint_terms: list[str] | None = None
    sample_text: str | None = None
    account_id: str | None = None


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


@router.get("/services", response_model=list[Service])
async def list_services() -> list[Service]:
    """`API-07`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/services", response_model=Service)
async def create_service(payload: ServiceCreate) -> Service:
    """`API-08`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/services/{id}", response_model=Service)
async def get_service(id: str) -> Service:
    """`API-09`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/services/{id}", response_model=Service)
async def update_service(id: str, payload: ServiceUpdate) -> Service:
    """`API-10`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/services/{id}/questions", response_model=list[SignalQuestion])
async def list_questions(id: str) -> list[SignalQuestion]:
    """`API-11`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/services/{id}/questions", response_model=SignalQuestion)
async def create_question(id: str, payload: SignalQuestionCreate) -> SignalQuestion:
    """`API-12`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/questions/{id}", response_model=SignalQuestion)
async def update_question(id: str, payload: SignalQuestionUpdate) -> SignalQuestion:
    """`API-13`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/questions/preview", response_model=QuestionPreview)
async def preview_question(payload: QuestionPreviewRequest) -> QuestionPreview:
    """`API-14`."""
    raise AssertionError("unreachable: contract_not_built already raised")
