"""Router of the [Evaluation](/architecture/interfaces.md#evaluation-contracts) family:
`API-50` to `API-55`, `API-77`. `API-77` `GET /impact` is built; every other route is a declared
stub answering `501 NOT_IMPLEMENTED`.

`API-77` ships with no role dependency yet (the recorded deviation of
`.work/impact-panel/design.md`), so no `403`/`401` role test is written for it; issue #11 adds it
beside the guard it exercises."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.common import Page
from leadradar.api.router_utils import stub_router
from leadradar.api.runs_and_plugins import Run
from leadradar.api.services_and_questions import QuestionOption
from leadradar.clock import now
from leadradar.core.enums import (
    DocumentTriageClassifier,
    EvaluationItemOrigin,
    EvaluationItemStatus,
    FindingStrength,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
)
from leadradar.db.session import get_session
from leadradar.evaluation.impact import read_impact

router = APIRouter(tags=["evaluation"])
evaluation_stub_router = stub_router("evaluation")


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
    """[`Impact`](/architecture/interfaces.md#impact), the response of `API-77`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_days: int
    accounts_refreshed: int
    refreshes: int
    cost_per_refresh_eur: float | None
    minutes_per_refresh: float | None
    findings_created: int
    precision: float | None
    labelled_items: int | None
    manual_minutes_per_account: int
    manual_hours_replaced: float


@evaluation_stub_router.get("/evaluation/label-queue", response_model=LabelQueue)
async def get_label_queue(service_id: str) -> LabelQueue:
    """`API-50`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@evaluation_stub_router.post("/evaluation/items", response_model=EvaluationItem)
async def create_label(payload: LabelCreate) -> EvaluationItem:
    """`API-51`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@evaluation_stub_router.get("/evaluation/items", response_model=Page[EvaluationItem])
async def list_evaluation_items(
    question_id: str | None = None,
    origin: EvaluationItemOrigin | None = None,
    status: EvaluationItemStatus | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> Page[EvaluationItem]:
    """`API-52`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@evaluation_stub_router.post("/evaluation/runs", response_model=Run, status_code=202)
async def start_evaluation_run() -> Run:
    """`API-53`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@evaluation_stub_router.get("/evaluation/results", response_model=list[EvaluationResultSummary])
async def list_evaluation_results() -> list[EvaluationResultSummary]:
    """`API-54`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@evaluation_stub_router.get("/evaluation/results/{run_id}", response_model=EvaluationResult)
async def get_evaluation_result(run_id: str) -> EvaluationResult:
    """`API-55`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/impact")
async def get_impact(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Impact:
    """`API-77`: computed on read by [Impact](/architecture/rules.md#impact); writes nothing."""
    settings = request.app.state.settings
    current_time = now(fixture_mode=settings.fixture_mode, clock_file=settings.clock_file)
    report = await read_impact(session, settings, current_time)
    return Impact(
        period_days=report.period_days,
        accounts_refreshed=report.accounts_refreshed,
        refreshes=report.refreshes,
        cost_per_refresh_eur=report.cost_per_refresh_eur,
        minutes_per_refresh=report.minutes_per_refresh,
        findings_created=report.findings_created,
        precision=report.precision,
        labelled_items=report.labelled_items,
        manual_minutes_per_account=report.manual_minutes_per_account,
        manual_hours_replaced=report.manual_hours_replaced,
    )
