"""Router of the [Evaluation](/architecture/interfaces.md#evaluation) family: `API-50` to `API-55`,
`API-77`. Every route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from leadradar.api.common import Page
from leadradar.api.router_utils import stub_router
from leadradar.api.runs_and_plugins import Run
from leadradar.api.services_and_questions import QuestionOption
from leadradar.core.enums import (
    DocumentTriageClassifier,
    EvaluationItemOrigin,
    EvaluationItemStatus,
    FindingStrength,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
)

router = stub_router("evaluation")


class LabelTaskQuestion(BaseModel):
    """`LabelTask.question`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    key: str
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[QuestionOption] | None
    polarity: SignalQuestionPolarity


class LabelTaskAccount(BaseModel):
    """`LabelTask.account`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str


class LabelTaskDocument(BaseModel):
    """`LabelTask.document`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    url: str
    language: str
    published_at: str | None


class LabelTask(BaseModel):
    """[`LabelTask`](/architecture/interfaces.md#labeltask)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    passage_text: str
    question: LabelTaskQuestion
    question_revision: int
    account: LabelTaskAccount
    document: LabelTaskDocument


class LabelQueue(BaseModel):
    """[`LabelQueue`](/architecture/interfaces.md#labelqueue)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tasks: list[LabelTask]
    active_items: int
    min_items: int


class LabelCreate(BaseModel):
    """[`LabelCreate`](/architecture/interfaces.md#labelcreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    question_id: str
    question_revision: int
    expected_strength: FindingStrength


class EvaluationItem(BaseModel):
    """[`EvaluationItem`](/architecture/interfaces.md#evaluationitem)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    chunk_id: str
    question_id: str
    question_revision: int
    created_at: str
    question_key: str
    expected_strength: FindingStrength
    origin: EvaluationItemOrigin
    status: EvaluationItemStatus
    labelled_by_name: str


class EvaluationResultSummary(BaseModel):
    """[`EvaluationResultSummary`](/architecture/interfaces.md#evaluationresultsummary)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    created_at: str
    classifier: DocumentTriageClassifier
    items: int
    passed: bool
    precision: float | None
    recall: float | None
    escalation_rate: float | None


class EvaluationResultErrorEntry(BaseModel):
    """One entry of `EvaluationResult.metrics.errors`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_key: str
    passage_text: str
    document: dict[str, str]


class EvaluationResult(EvaluationResultSummary):
    """[`EvaluationResult`](/architecture/interfaces.md#evaluationresult): every field of
    [`EvaluationResultSummary`](#evaluationresultsummary) plus these."""

    escalation_lower: float
    escalation_upper: float
    min_precision: float
    min_items: int
    escalation_rate_target: float
    metrics: dict[str, object]


class Impact(BaseModel):
    """[`Impact`](/architecture/interfaces.md#impact)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_days: int
    accounts_refreshed: int
    refreshes: int
    findings_created: int
    cost_per_refresh_eur: float | None
    minutes_per_refresh: float | None
    precision: float | None
    labelled_items: int | None
    manual_minutes_per_account: int
    manual_hours_replaced: float


@router.get("/evaluation/label-queue", response_model=LabelQueue)
async def get_label_queue(service_id: str) -> LabelQueue:
    """`API-50`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/evaluation/items", response_model=EvaluationItem)
async def create_label(payload: LabelCreate) -> EvaluationItem:
    """`API-51`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/evaluation/items", response_model=Page[EvaluationItem])
async def list_evaluation_items(
    question_id: str | None = None,
    origin: EvaluationItemOrigin | None = None,
    status: EvaluationItemStatus | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> Page[EvaluationItem]:
    """`API-52`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/evaluation/runs", response_model=Run, status_code=202)
async def start_evaluation_run() -> Run:
    """`API-53`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/evaluation/results", response_model=list[EvaluationResultSummary])
async def list_evaluation_results() -> list[EvaluationResultSummary]:
    """`API-54`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/evaluation/results/{run_id}", response_model=EvaluationResult)
async def get_evaluation_result(run_id: str) -> EvaluationResult:
    """`API-55`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/impact", response_model=Impact)
async def get_impact() -> Impact:
    """`API-77`."""
    raise AssertionError("unreachable: contract_not_built already raised")
